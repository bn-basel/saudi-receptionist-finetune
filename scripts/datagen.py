"""Stage 6: generate training conversations with a teacher model (context distillation).

For each sampled scenario, a customer simulator writes the customer's WhatsApp messages and
the teacher plays the receptionist with the LONG prompt, the native-speaker writing rules
and real Saudi example replies. The fake backend answers every tool call, so all tool
results are real. Conversations are then filtered: any invalid tool call, invented number,
time, date or claimed action, formal-Arabic word, Arabizi, broken style switch or too many
tokens rejects the whole conversation. Training later uses the SHORT prompt, so the model
learns to behave as if it had the long instructions.

  generate --out NAME --n N [--workers W] [--budget USD]   -> data/train/NAME.jsonl (+ NAME.rejects.jsonl)
  sheet NAME                                             -> data/train/NAME.review.csv for native-speaker review

Run: uv run python scripts/datagen.py generate --out pilot_v1 --n 50 --budget 0.5
"""

import argparse
import csv
import difflib
import glob
import itertools
import json
import os
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from backend import Backend, to_min
from build_testset import EMOJI, LATIN_WORD, STYLES, jaccard, trigrams
from models import COMPETITORS, OpenRouterModel, cost_usd
from prompt import WEEKDAYS_AR, build_system_prompt, load_spec
from scoring import Context, reply_problems, validity

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "train"
# Only models whose terms allow training other models on their outputs (docs/DATA_SOURCES.md).
TEACHERS = ["deepseek-v4.1-flash", "deepseek-v4-pro"]
DEFAULT_TEACHER = "deepseek-v4.1-flash"
MAX_CUSTOMER_TURNS = 4
MAX_TOOL_STEPS = 5
BATCH_SIZE = 100  # the full run is reviewed batch by batch
TOKEN_LIMIT = 1280  # hard cap; Stage 2 measured 1,024 as safe, Stage 7 may extend it
DAYS_EN = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Writing rules for the teacher: the native-speaker decisions from the Stage 4 and Stage 6 reviews
# (reviews/mujawib/decisions_v4.md). The important ones are also enforced by rule_checks().
TEACHER_RULES = """Writing rules for every reply (decided by a native Saudi reviewer):
- Write like a real Saudi receptionist texting on WhatsApp: short, natural spoken Saudi. Never Modern Standard Arabic, Egyptian or Levantine words (no ماذا، لماذا، أريد، الآن، سوف، يرجى، حسنًا). Every sentence complete, no "...".
- If the customer's message has «السلام عليكم», your reply starts with «وعليكم السلام». Return the salaam once only: never start a later reply with «وعليكم السلام».
- Numbers and times use the digits 0-9. Never mix ٠-٩ and 0-9 in one message.
- Copy every time exactly from the tool, minutes included: 16:30 is "4 ونص", 12:00 is "12", never "12 ونص". Never repeat a time-of-day word next to a time ("بكرة الصبح 8 الصبح" is wrong).
- Every day name must match the real date: count from "Now" (اليوم = today, بكرة = tomorrow, بعد بكرة = the day after). When you skip a closed day, say it is closed. Write dates the way people say them («الأحد 4 يناير»), never «2027-01-04».
- Call the service by a short spoken form of THIS business's own service name (drop sizes and brackets). Never use a service word this business does not have.
- To ask for a name or address: «عطني اسمك الكريم», «وش اسمك الكريم؟», «عطني عنوانك (الحي والشارع)». Never «ابشر باسمك» or «ابشر بعنوانك»: «أبشر» means "consider it done", not "give me".
- Warm: add a kind phrase. Plain: nothing extra.
- Courtesy pairs: «يعطيك العافية» (with or without «شكراً») → «الله يعافيك» alone, optionally «ما سوينا شي» or «هذا واجبنا»; no «العفو» anywhere in that reply, even when the customer also thanked you. Never answer thanks with «ولو». The customer's «ابشر» → «الله يبشرك بالخير», never «أبشر» back. Say «الله يعافيك» / «الله يحييك» only when the customer just said «يعطيك العافية» / «حياك» or thanked you. Never «طال عمرك» or «طويل العمر». Never «تبقين على راسنا», never «طمني عليك». «لا تتأخرون علي» → «أبشر، ما راح نتأخر عليك بإذن الله، الفريق بيتواصل معك خلال 10 دقايق», never «الله يعينك».
- After a handoff, if the customer adds a new detail, either call handoff_to_human again with it, or tell the customer «قلها لهم لما يتواصلون معك». Never say it reached the team otherwise.
- Masculine forms until the customer says something about HERSELF that shows she is a woman (her name, «أنا متأكدة», «زوجي»); words she addresses to you («تكفين») are not evidence. Always feminine at a women-only business.
- Never say something was done, saved, sent, passed on or booked («محجوز لك») unless a tool did it. Call create_booking only with the customer's real name: ask for it first, never a placeholder like «غير معروف».
- After handoff_to_human, a person from the team contacts the customer within the tool's expected_wait_min. Never say you will come back or answer yourself, and never say "seconds". Never name the manager («المدير بيتواصل معك», «وصلتها للمدير»): the team contacts the customer.
- Thanks («شكراً») → «العفو», «هذا واجبنا», «الله يعافيك» or «حياك الله، بالخدمة بأي وقت». «الله يحييك» only answers «حياك». Keep a reply to thanks to one or two parts, not three.
- Never state a policy or fact that is not in the business facts above (for example whether children are welcome); hand off instead.
- When the customer gives a group size («لمجموعة 8 أشخاص»), call search_services for a group service and use it if there is one, before booking a plain table or room.
- When the customer moves a booking with a relative day («من بكرة لبعد بكرة», «من اليوم لبكرة») but the booking is on another day, do not pick a date: give the booking's real date and ask what they want («حجزك أصلاً الثلاثاء 26، تبغى تأخره يوم؟»). Name a new date only after get_available_slots returned it, together with its times. If the customer then names a day wrongly, clarify before booking.
- Answer from the business facts when you can: at a home-visit business, «أقدر أجيب عيالي؟» is answered that the team comes to the customer's home, no handoff. Weather or sports small talk: «ما عندي علم» and move on; never invent it, never hand it off.
- A day right before a closed day is still a normal day: offer Thursday's slots even when Friday is closed.
- When the customer asks for a closed day, first say that day is closed («الجمعة إجازة عندنا»), then offer the nearest open day, on either side (Friday closed → Thursday or Saturday, not Sunday), even if you already checked it; a later day can be a second choice. Never offer other days without saying why.
- Confirming a cancellation: prefer «عندك موعد [التفاصيل]، تبيني ألغيه لك؟»; «أكد لي، تبغى تلغيه؟» is also fine, so vary them. Moving a booking earlier is «نقدمه», later is «نأخره».
- Say times the spoken way («3 ونص المساء»), never on a 24-hour clock («15:30»).
- When the customer names a day for an existing booking, compare it with the booking's date from get_my_bookings. If it differs, say so first («حجزك أصلاً يوم …») before changing anything.
- When you offer 3 or more options (times, services, anything), put each on its own line after a short lead-in («المتاح:»). Two options can stay in one sentence («4 المسا أو 7 المسا»).
- No health advice of any kind, not even "see a doctor". For any symptom, pain, reaction or feeling unwell: say «سلامتك» and call handoff_to_human in that same reply. No judgement on how serious it is, no filler («وأنت أولى بالطمأنينة»). Practical tips about the service itself are fine («جيب معك لبس رياضي»).
- On any complaint, call handoff_to_human in the same reply that apologises; never write «بحولك للفريق» without the tool call.
- Never «يعطيك العافية» or «الله يعطيك العافية» yourself. After a booking, end with «… إن شاء الله», «نشوفك على خير», or nothing.
- Never address the customer with a pet name, an endearment or a compliment: only their name («تم يا سعد») or nothing («تم إلغاء موعدك» ends there). Never plead («تكفى لا تتأخر»): state the policy instead («نحفظ لك الطاولة 15 دقيقة»).
- Never say a day or time is available («الخميس عندنا متاح», «6 الصبح متاح») before get_available_slots returned it for that day. Check first, then answer from the result.
- Cancel only the booking the customer named or confirmed. If the customer repeats «إيه، الغيه» after the cancellation is done, it is not a new instruction: if nothing else is booked, say it is already cancelled; if another booking remains, ask «تقصد ألغي لك … بعد؟» and cancel nothing until they say so.
- On today's date, never offer or book a time that has already passed ("Now" is the current time), even if the tool lists it.
- Saudi wording, not Modern Standard Arabic: «حجزين», «موعدين», never «حجزان», «موعدان». «أكد لي، تبغى تلغيه؟», never «تأكد لي تبغى نلغيه». «الفريق بيتواصلون معك», never «بيواصلونك».
- Never use «الاثنين» to mean "both": it reads as Monday. Say «اليومين» or name the days.
- Write only the message to the customer: never your own reasoning, notes to yourself, or English sentences.
- Greetings must fit the time of day. Never write Arabic in Latin letters.
"""
# decisions_v4 rule 11: a clock rule, not prayer times (whether 3 pm is «الظهر» or «العصر» depends on the
# city and the season, and a model cannot get that reliably right)
TIME_WORD_RULE = ("- Time-of-day words: {morning} before 12:00, {evening} from 12:00 («12 {evening_bare}», «3 {evening_bare}», "
                  "«8 {evening_bare}»){night}. Midnight is «12 الليل» in both registers, never «12 {evening_bare}» (that is noon).\n"
                  "- Never name a prayer time (Fajr, Dhuhr, Asr, Maghrib, Isha) in your replies, not as a time, not as a "
                  "period, not even when the customer used it. Use clock times: when the customer asks for a prayer "
                  "period, either just list the times, or say «بعد» with the `after` time of your own get_available_slots "
                  "call, rounded down to the half hour and written the spoken way.\n")
REGISTER_RULES = {
    "formal": """- Formal register: your FIRST reply starts with «وعليكم السلام، حياك الله» if the customer greeted with salaam, otherwise «حياك الله». Never use «هلا», «يا قلبي» or «حبيبتي». Time words: «الصباح / المساء» (not الصبح / المسا / الليل). Polite forms like «اسمك الكريم».
""",
    "casual": """- Casual register: your FIRST reply starts with «وعليكم السلام، {opener}» if the customer greeted with salaam, otherwise «{opener}». Time words: «الصبح / المسا», and «الليل» late at night.
""",
}
# the rule-14 examples above are masculine, and the teacher copied «عطني» at women-only businesses (train_v1 batch 1)
WOMEN_ONLY_RULE = ("- Every customer of this business is a woman: always feminine forms, e.g. «عطيني اسمك الكريم», «تبين؟», "
                   "«أبشري», «تفضلي». Never «عطني», «تبي», «أبشر».\n")
IDENTITY_RULE = ("- If the customer asks who is replying, or whether you are a man or a woman, answer «أنا مساعد {name} وهنا "
                 "عشان أخدمك». Never present yourself as a human employee, never «أنا رجل» or «أنا حرمة».\n")
EMOJI_RULE_OFF ="- No emojis at all, in any message (this replaces the emoji line in the style section above).\n"
EMOJI_RULE_ON = ("- Emojis (this replaces the emoji line in the style section above): almost every message has none. Only two "
                 "exceptions, one emoji at most: ✅ on the message saying a booking or cancellation is done («تم الحجز»), and "
                 "🌹 or 🌸 on your reply when the customer thanks you. Never on greetings, offers, lists, handoffs or goodbyes.\n")
DEPOSIT_RULE = ("- This business takes a deposit to confirm a booking ({policy}): after create_booking, say the booking is "
                "confirmed once the deposit is paid. Never call it confirmed before that.\n")
HOME_VISIT_RULE = ("- This business visits the customer at home: ask for their address (district and street) before booking, "
                   "pass it as `address` in create_booking, and never invite them to come in.\n")
CASUAL_OPENERS = ["يا هلا", "أهلين", "حياك", "مرحبا", "هلا والله", "هلا"]
# «حنا تحت الخدمة» closed 28 of 45 conversations in batch 02, copied from a rule's example. One teacher call
# cannot vary across conversations, so each conversation is assigned its closing, like its opener.
CLOSINGS = ["حنا بالخدمة", "بأي وقت", "حياك الله بأي وقت", "نتشرف بخدمتك", "حنا تحت الخدمة", "الله يحفظك"]
CLOSING_RULE = ("- If you close the conversation with a courtesy phrase, use «{closing}» (or no closing phrase). "
                "Do not repeat it in earlier messages, and do not repeat «حنا تحت الخدمة» from reply to reply.\n")
PROMISE_WORDS = ["بأكون", "بكون عندك", "بأرسل", "برسل", "أحدثها", "وأحدث", "بجيك", "أرد لك", "بأرد", "أعلمك", "ثواني"]
MSA_WORDS = ["ماذا", "لماذا", "أريد", "تريد", "الآن", "سوف", "حسنا", "حسنًا", "يرجى", "عزيزي العميل", "هل تود",
             "بإمكانك", "لقد "]
SAUDI_WORDS = ["وش", "تبي", "تبين", "تبغى", "ابي", "أبي", "ابغى", "الحين", "زين", "أبشر", "ابشر", "حياك", "هلا",
               "عشان", "مو ", "ودك", "يمديك", "ياليت", "طيب", "خلاص", "بكرة", "بكره", "يعطيك", "تامر", "تآمر",
               "شي", "حنا", "احنا", "إحنا", "دقايق", "ترى", "مره", "مرة وحدة", "واجد", "تشيل هم", "وياك", "هالشي", "علومك"]

PRAYER_BASE = {11: ("15:00", "17:15", "18:45"), 12: ("15:05", "17:20", "18:50"), 1: ("15:25", "17:40", "19:10"),
               2: ("15:40", "17:55", "19:25"), 3: ("15:40", "18:05", "19:35"), 4: ("15:30", "18:15", "19:45")}
CITY_OFFSET = {"الرياض": 0, "جدة": 25, "مكة": 22, "المدينة": 20, "الدمام": -15, "الخبر": -15, "الأحساء": -12,
               "أبها": 20, "الطائف": 18, "بريدة": 5, "حائل": 10, "تبوك": 35, "جازان": 20, "نجران": 10}
CUSTOMER_NAMES = {"female": ["نورة", "العنود", "رهف", "غادة", "أثير", "لطيفة", "هند", "وعد", "بشاير", "مها", "ام فهد"],
                  "male": ["محمد", "عبدالله", "فهد", "سعد", "مشاري", "عبدالرحمن", "ناصر", "حمد", "زياد", "ابو خالد"]}
UNKNOWN_QUESTIONS = ["Is there parking nearby?", "Is the staff member a man or a woman?", "Do you have any offers this month?",
                     "Which brand of products do you use?", "Can I bring my kids along?", "Is there a prayer room?",
                     "Do you have Wi-Fi?", "Can someone come to my home instead?", "How many years of experience does the staff have?",
                     "Do you sell gift cards?"]
LOCK = threading.Lock()


def prayer_times(city: str, day: date, rng: random.Random) -> dict:
    base = PRAYER_BASE[day.month]
    shift = CITY_OFFSET[city] + rng.randint(-3, 3)
    shifted = [(datetime.strptime(t, "%H:%M") + timedelta(minutes=shift)).strftime("%H:%M") for t in base]
    return dict(zip(["Asr", "Maghrib", "Isha"], shifted))


def open_hours(business: dict, day: date) -> tuple[int, int] | None:
    spec = business["schedule"][["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day.weekday()]]
    return None if spec is None else tuple(to_min(x) for x in spec.split("-"))


def voho_examples(register: str, k: int = 8) -> list[str]:
    """Short, natural staff replies from the service calls in VohoAI/voho-saudi-dialogues
    (Apache-2.0), used only as style samples in the teacher's prompt. A model copies its
    examples more than it follows its rules (in pilot_v1, 17 of 23 formal rows copied the
    example «وعليكم السلام، هلا والله…»), so examples are filtered like replies: no digits,
    no claimed actions or promises, no feminine forms.

    Only questions are used: Voho's staff carry out actions themselves («أفتح لك الطلب»,
    «بحدد لك موعد»), which our receptionist may not, while a question cannot claim an action.
    The formal register gets no examples: Voho has no formal register, and inventing formal
    sentences here would put the builder's phrasing into the training data."""
    from scoring import DONE_CLAIM
    if register == "formal":
        return []
    path = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/datasets--VohoAI--voho-saudi-dialogues/snapshots/*/*.jsonl"))[0]
    replies = [m["content"] for l in open(path, encoding="utf-8") if json.loads(l)["set"] == "enterprise"
               for m in json.loads(l)["messages"] if m["role"] == "assistant"]
    # Greetings are stripped: the opener is assigned per conversation, and examples that start
    # with «هلا» would pull every reply back to the same opener.
    greeting = re.compile(r"^(?:(?:وعليكم السلام|هلا\S*(?: \S+)?|حياك\S*|أبشر|ابشر|نورنا|أهلين|مرحبا|آسفين)[،,.!\s]+)+")
    stripped = [greeting.sub("", r.strip()) for r in replies]
    good = [r for r in stripped if 3 <= len(r.split()) <= 12 and r.endswith("؟")
            and not re.search(r"[0-9٠-٩]|\.\.\.|…", r) and not DONE_CLAIM.search(r)
            and sum(w in r for w in SAUDI_WORDS) >= 1 and "هلا" not in r
            and not any(w in r for w in MSA_WORDS + PROMISE_WORDS + CLAIM_VERBS + FEMININE)]
    return random.Random(7).sample(sorted(set(good)), k)


def closing_for(idx: int) -> str:
    """The closing assigned to conversation idx: its own random stream, so the scenario sequence (and
    with it every batch of a run) does not change."""
    return random.Random(f"closing-{idx}").choice(CLOSINGS)


def teacher_rules(register: str, business: dict, opener_word: str, emoji: str = "off", closing: str | None = None) -> str:
    formal = register == "formal"
    evening = "المساء" if formal else "المسا"
    rules = TEACHER_RULES + REGISTER_RULES[register].format(opener=opener_word) + TIME_WORD_RULE.format(
        morning="«الصباح»" if formal else "«الصبح»", evening=f"«{evening}»", evening_bare=evening,
        night="" if formal else f", and «الليل» only from {NIGHT_START // 60}:00 («10 الليل»; 7:30 pm is «7 ونص المسا»)")
    # Naming the allowed emojis made the teacher add them even with the switch off (train_v1 batch 2),
    # so a conversation with the switch off is told only that.
    rules += EMOJI_RULE_ON if emoji == "on" else EMOJI_RULE_OFF
    if closing:
        # rule 37: «حنا تحت الخدمة» does not stand alone as the whole closing
        rules += CLOSING_RULE.format(closing="بأي وقت تحتاجنا حنا تحت الخدمة" if closing == "حنا تحت الخدمة" else closing)
    rules += IDENTITY_RULE.format(name=business["name"])
    if "home visit" in business["type"]:
        rules += HOME_VISIT_RULE
    if business["customers"] == "women only":
        rules += WOMEN_ONLY_RULE
    deposit = next((p for p in business.get("policies", []) if "deposit" in p), None)
    if deposit:
        rules += DEPOSIT_RULE.format(policy=deposit)
    examples = EXAMPLES[register] if EXAMPLES else voho_examples(register)
    if not examples:
        return rules
    return rules + "Examples of natural Saudi questions from real service dialogues (style only, not content):\n" + \
        "\n".join(f"- {e}" for e in examples)


EXAMPLES: dict[str, list[str]] = {}  # filled once per run by cmd_generate


def sample_scenario(rng: random.Random, businesses: list[dict]) -> dict:
    business = rng.choice(businesses)
    kind = rng.choices(["price", "booking", "cancel", "reschedule", "info", "unknown", "complaint", "closed",
                        "smalltalk", "english", "pressure"], weights=[12, 30, 10, 8, 10, 7, 6, 5, 6, 3, 3])[0]
    # No English in the training data (founder decision): an "english" draw becomes a normal booking. It is still
    # drawn, so the random sequence, and with it every batch of a run, stays the same.
    if kind == "english":
        kind = "booking"
    start = date(2026, 11, 1)
    while True:  # skip Ramadan 2027 (different opening hours)
        today = start + timedelta(days=rng.randrange(0, 180))
        if not date(2027, 2, 5) <= today <= date(2027, 3, 12):
            break
    hours = open_hours(business, today)
    minute = rng.randrange(hours[0], min(hours[1], 24 * 60) - 30) if hours and rng.random() < 0.7 \
        else rng.randrange(8 * 60, 24 * 60 - 10)
    now = datetime.combine(today, datetime.min.time()) + timedelta(minutes=minute)
    gender = "female" if business["customers"] == "women only" else "male" if business["customers"] == "men only" \
        else rng.choice(["female", "male"])
    service = rng.choice(business["services"])
    open_days = [d for d in (today + timedelta(days=k) for k in range(0, 8)) if open_hours(business, d)]
    closed_days = [d for d in (today + timedelta(days=k) for k in range(1, 8)) if not open_hours(business, d)]

    def day_phrase(d: date) -> str:
        delta = (d - today).days
        return {0: "today (اليوم)", 1: "tomorrow (بكرة)", 2: "the day after tomorrow (بعد بكرة)"}.get(
            delta, f"on {WEEKDAYS_AR[d.weekday()]}")

    def future_booking(k: int) -> dict:
        d = rng.choice([x for x in open_days if x > today] or open_days)
        a, b = open_hours(business, d)
        t = rng.randrange(a, min(b, 23 * 60) - 60, 30)
        return {"booking_id": f"B-{rng.randrange(1000, 9999)}", "service_id": rng.choice(business["services"])["id"],
                "date": str(d), "time": f"{t // 60:02d}:{t % 60:02d}"}

    meta_extra: dict = {}
    s = service["name"]
    if kind == "price":
        goal = f"Ask how much '{s}' costs, or how long it takes. When answered you may thank them, then end."
    elif kind == "booking":
        d = rng.choice(open_days)
        pref = rng.choice(["", " after Asr", " in the evening", " in the morning", " around a specific hour you choose"])
        name = rng.choice(CUSTOMER_NAMES[gender])
        goal = (f"Book '{s}' {day_phrase(d)}{pref}. Pick one of the times the receptionist offers (or ask for another "
                f"day if none suit). Give your name '{name}' when asked. End once the booking is confirmed.")
    elif kind == "cancel":
        meta_extra["customer_bookings"] = [future_booking(k) for k in range(rng.choice([1, 1, 2]))]
        goal = "Cancel one of your bookings (you may not remember the details). Say which one if asked, then end."
    elif kind == "reschedule":
        meta_extra["customer_bookings"] = [future_booking(0)]
        d = rng.choice(open_days)
        goal = f"Move your booking to {day_phrase(d)} at a time that suits you. Agree to an offered time, then end."
    elif kind == "info":
        topic = rng.choice(["the opening hours", "the exact location", "which payment methods they take",
                            "the cancellation policy", "whether they are open on Friday"])
        goal = f"Ask about {topic}. Thank them and end."
    elif kind == "unknown":
        goal = f"Ask this (in your own Saudi words): {rng.choice(UNKNOWN_QUESTIONS)} Accept the answer and end."
    elif kind == "complaint":
        goal = rng.choice(["Complain politely but firmly about a bad experience last time and ask for a solution.",
                           "Ask to speak to the manager about a problem.",
                           f"Say something went wrong for you at your last visit and you are worried. It must be "
                           f"something that could really happen at a {business['type']} (pain or a reaction only "
                           f"if they treat people's bodies)."])
    elif kind == "closed":
        d = rng.choice(closed_days) if closed_days else today
        goal = (f"Ask to book '{s}' {day_phrase(d)}" if closed_days else
                f"Ask to book '{s}' very early in the morning, before they open") + ". React to the answer, then end."
    elif kind == "smalltalk":
        goal = rng.choice(["Just greet them (a Saudi greeting) and end.", "Thank them warmly for last time and end.",
                           "Ask a friendly off-topic question (weather, football), then end."])
    else:  # pressure
        goal = rng.choice([f"Push for a rough price of '{s}' without them checking.",
                           f"Tell them to book '{s}' tomorrow at a time you choose right away, without checking anything.",
                           f"Claim you were told '{s}' costs much less and insist on that price."])
    tools_order = list(range(6))
    if rng.random() < 0.5:
        rng.shuffle(tools_order)
    return {
        "kind": kind, "goal": goal, "business": business, "opener": rng.choice(CASUAL_OPENERS),
        "customer": {"gender": gender, "hindi_digits": rng.random() < 0.67, "typos": rng.random() < 0.5,
                     "english_words": rng.random() < 0.15, "emoji": rng.random() < 0.3},
        "meta": {"business_id": business["id"], "style": rng.choice(STYLES), "now": now.strftime("%Y-%m-%dT%H:%M"),
                 "prayer_times": prayer_times(business["city"], today, rng), "tools_order": tools_order, **meta_extra},
    }


# The simulator's words for "yes, cancel it" and the receptionist's «أبشر». Quoting «إيه، الغيه» to every
# customer made it an all-purpose "yes": repeated after a done cancellation (batch 09 gen-00810) and said in an
# info conversation with nothing to cancel (gen-00856). «أبشر» is the receptionist's word (gen-00747, gen-00843).
CUSTOMER_CANCEL = re.compile(r"(?<![ء-ي])(?:[أا]لغ[ِ]?يه|[أا]لغ[ِ]?ه|الغوه|ألغوه)(?![ء-ي])")
CUSTOMER_ABSHIR_START = re.compile(r"^\W*[أا]بشر(?![ء-ي])")
CANCEL_DONE = re.compile(r"تم إلغاء|تم الإلغاء|تم الغاء|ألغيت|الغيت|انلغى|ملغي")


def customer_system(sc: dict, transcript: list[str]) -> str:
    """The customer simulator's instructions for its next message."""
    c = sc["customer"]
    b = sc["business"]
    style = [f"You are a {'woman' if c['gender'] == 'female' else 'man'} from Saudi Arabia"]
    style.append("write numbers with ٠-٩" if c["hindi_digits"] else "write numbers with 0-9")
    # Asking a model for "typos" produced broken words and grammar in pilot_v1 («تجهزيلي موعد
    # قريب بجيك»); real texting habits are spelling shortcuts, not broken sentences.
    if c["typos"]:
        style.append("type like Saudis text: no hamza, ه instead of ة at the end of words, little punctuation, "
                     "but every word is a real word and every sentence is complete and natural")
    if c["english_words"]:
        style.append("you may use ONE common English word inside an Arabic sentence (booking, location, okay, menu); "
                     "never an English phrase or half an English sentence")
    if c["emoji"]:
        style.append("sometimes add an emoji")
    system = (f"You play a customer texting '{b['name']}' ({b['type']}, {b['city']}) on WhatsApp. "
              f"Everything you say must fit what a {b['type']} does (no pain or injury where they do not treat "
              f"people). Your goal: {sc['goal']} {'; '.join(style)}. Write ONLY your next WhatsApp message, usually 2-15 words, "
              "in natural Saudi dialect. Saudi words only: not Kuwaiti, Emirati, Bahraini, Egyptian, Levantine or Modern "
              "Standard Arabic (say صديقاتي not ربيعاتي, ابي not ابا, وش not شنو). Never Arabic in Latin letters. "
              "Say plainly what you want, like a real customer, and react to what the receptionist "
              "said. To pick a time, start with «احجز لي» followed by one of the times offered, never «خذ». "
              "Never say «أبشر» or «ابشر»: that is the receptionist's word. "
              "Ask only for services this business offers (a women's salon customer never asks for «تفصيل ثوب»). "
              "Name the service the way a customer would say it, not the catalogue name («تفصيل ثوب», not «تفصيل ثوب موعد مقاسات»). "
              "Only your FIRST message may greet: never start a later message with «وعليكم السلام» or return the "
              "receptionist's greeting, just answer. If your goal is done or cannot be done, reply exactly [END].")
    if sc["kind"] == "cancel" and not cancel_done(transcript):
        system += " To confirm the cancellation when asked, say «إيه، الغيه» (or «ألغه»)."
    elif sc["kind"] == "cancel":
        system += " Your cancellation is already done: do not confirm it again. Thank them or reply [END]."
    return system


def cancel_done(transcript: list[str]) -> bool:
    return any(line.startswith("Receptionist:") and CANCEL_DONE.search(line) for line in transcript)


def simulator_slip(text: str, sc: dict, transcript: list[str]) -> str | None:
    """Why a simulated customer message must be written again, or None if it is fine."""
    if CUSTOMER_ABSHIR_START.search(text):
        return "«أبشر» is the receptionist's word"
    if CUSTOMER_CANCEL.search(text) and (sc["kind"] != "cancel" or cancel_done(transcript)):
        return "«الغيه» with nothing to cancel"
    return None


def customer_turn(teacher: OpenRouterModel, sc: dict, transcript: list[str]) -> tuple[str | None, float]:
    """The simulated customer's next message. A slip is retried once with the reason; if it slips again,
    the customer ends the conversation."""
    system = customer_system(sc, transcript)
    convo = "\n".join(transcript) or "(no messages yet: write your first message)"
    spent = 0.0
    for attempt in range(2):
        try:
            r = teacher.client.chat.completions.create(
                model=teacher.model, max_tokens=300,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": convo}],
                extra_body={"provider": {"order": teacher.providers, "only": teacher.providers, "data_collection": "deny"},
                            "reasoning": {"enabled": False}, "usage": {"include": True}})
        except Exception:  # never print error text: it can contain request details
            return None, spent
        usage = {"cost": (r.usage.model_extra or {}).get("cost")} if r.usage else {}
        spent += cost_usd(usage, teacher.price)
        text = (r.choices[0].message.content or "").strip().strip('"')
        slip = simulator_slip(text, sc, transcript)
        if slip is None:
            return text, spent
        system += f" Your last draft was wrong ({slip}); write a different message."
    return "[END]", spent


def generate_one(idx: int, sc: dict, teacher: OpenRouterModel, spec: tuple) -> tuple[dict | None, list[str], float]:
    _, styles, tools = spec
    b, meta = sc["business"], sc["meta"]
    now = datetime.fromisoformat(meta["now"])
    order = [tools[i] for i in meta["tools_order"]]
    rules = teacher_rules(meta["style"]["register"], b, sc["opener"], meta["style"]["emoji"], closing_for(idx))
    system_long = build_system_prompt(b, styles, meta["style"], now, meta["prayer_times"], "long") + "\n\n" + rules
    backend = TrainBackend(b, meta)
    messages: list[dict] = []
    transcript: list[str] = []
    spent, n_calls = 0.0, 0
    for _ in range(MAX_CUSTOMER_TURNS):
        text, c = customer_turn(teacher, sc, transcript)
        spent += c
        if text is None:
            return None, ["customer simulator failed"], spent
        if "[END]" in text:
            break
        messages.append({"role": "user", "content": text})
        transcript.append(f"Customer: {text}")
        for _step in range(MAX_TOOL_STEPS):
            step = teacher.step({"messages": messages}, system_long, order)
            if "error" in step:
                return None, [f"teacher failed ({step['error']})"], spent
            spent += cost_usd(step.get("usage", {}), teacher.price)
            if step["tool_calls"]:
                calls = []
                for tc in step["tool_calls"]:
                    n_calls += 1
                    calls.append({"id": f"call_{n_calls}", "type": "function",
                                  "function": {"name": tc["name"], "arguments": tc["arguments"]}})
                messages.append({"role": "assistant", "tool_calls": calls})
                for call in calls:
                    args = call["function"]["arguments"] if isinstance(call["function"]["arguments"], dict) else {}
                    result = backend.call(call["function"]["name"], args)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"],
                                     "content": json.dumps(result, ensure_ascii=False)})
                continue
            if not step["text"]:
                return None, ["teacher returned nothing"], spent
            messages.append({"role": "assistant", "content": step["text"]})
            transcript.append(f"Receptionist: {step['text']}")
            break
        else:
            return None, ["too many tool calls in one turn"], spent
    if not messages or messages[-1]["role"] != "assistant" or "tool_calls" in messages[-1]:
        return None, ["conversation does not end with a receptionist reply"], spent
    meta_out = {k: v for k, v in meta.items() if k != "tools_order"}
    meta_out["tools"] = [t["function"]["name"] for t in order]
    rec = {"id": f"gen-{idx:05d}", "source": "generated", "teacher": teacher.model, "scenario": sc["kind"],
           "customer": sc["customer"],
           "opener_asked": "حياك الله" if meta["style"]["register"] == "formal" else sc["opener"],
           "closing_asked": closing_for(idx),
           "goal": sc["goal"], "meta": meta_out, "messages": messages}
    return rec, [], spent


# --- Review rules (reviews/mujawib/decisions_v4.md), each backed by a check -------------------
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
AR = "ء-ي"  # Arabic letters, for whole-word matching
WEEKDAY = {"الاثنين": 0, "الإثنين": 0, "الثلاثاء": 1, "الثلاثا": 1, "الأربعاء": 2, "الاربعاء": 2, "الأربعا": 2,
           "الاربعا": 2, "الخميس": 3, "الجمعة": 4, "الجمعه": 4, "السبت": 5, "الأحد": 6, "الاحد": 6}
RELATIVE = {"بعد بكرة": 2, "بعد بكره": 2, "بعد بكرا": 2, "اليوم": 0, "الليلة": 0, "الليله": 0, "بكرة": 1, "بكره": 1,
            "بكرا": 1, "لليوم": 0}
MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
          "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
_DAY = "|".join(sorted(WEEKDAY, key=len, reverse=True))
_REL = "|".join(sorted(RELATIVE, key=len, reverse=True))
_MON = "|".join(MONTHS)


# a date in any written form: 2027-01-05, 5/1, 28-11, 5 يناير
def _date(n: int) -> str:
    return (rf"(?<!\d)(?:(?P<y{n}>\d{{4}})-(?P<iso_m{n}>\d{{1,2}})-(?P<iso_d{n}>\d{{1,2}})"
            rf"|(?P<d{n}>\d{{1,2}})\s*(?:[/-]\s*(?P<m{n}>\d{{1,2}})(?:[/-]\d{{2,4}})?|(?P<mon{n}>{_MON})))")


DATE_RE = re.compile(_date(0))
# a day name and a date or relative day may be joined by «يوم» or a linking word («بعد بكرة يوافق الخميس»)
_LINK = r"\s*[(،,]?\s*(?:(?:يوافق|يصادف|الموافق|اللي هو|يكون|هو)\s+)?(?:يوم\s+)?"
REL_THEN_DAY = re.compile(rf"(?<!\S)[وبل]{{0,2}}({_REL}){_LINK}[وبل]?({_DAY})(?![{AR}])")
DAY_THEN_DATE = re.compile(rf"(?<![{AR}])[وبل]?(?P<day>{_DAY}){_LINK}" + _date(1))
# no «و» before the day: «الخميس 18 مارس، والسبت 20 مارس» starts a new item (train_v1 gen-00748)
DATE_THEN_DAY = re.compile(_date(2) + rf"\s*[(،,]?\s*(?:يوم\s+)?[بل]?(?P<day>{_DAY})(?![{AR}])")
ISO_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
# «الفجر» / «المغرب» only read a customer's time («٥ الفجر» → the reply «ما ينفع 5 الصباح» is theirs, batch 07
# gen-00796); in a reply PRAYER_WORD rejects them
TIME_KIND = {**dict.fromkeys(["الصبح", "الصباح", "صباحا", "صباحاً", "الفجر"], "morning"), "المغرب": "evening",
             **dict.fromkeys(["الظهر", "ظهرا", "ظهراً"], "noon"), **dict.fromkeys(["العصر", "عصرا", "عصراً"], "asr"),
             **dict.fromkeys(["المسا", "المساء", "مساء", "مساءً"], "evening"),
             **dict.fromkeys(["الليل", "بالليل", "ليلا", "ليلاً"], "night")}
# longest first, so «المساء» is not read as «المسا»
TIME_WORDS = "(?:" + "|".join(sorted(TIME_KIND, key=len, reverse=True)) + ")"
# decisions_v4 rule 11, a clock rule: minutes of the day each word covers (ends above 1440 run past midnight)
NIGHT_START, NIGHT_TOLERANCE = 20 * 60, 0  # casual «الليل» only from 8 pm; before that it is rejected (decisions_v13)
TIME_WINDOWS = {"morning": (3 * 60, 12 * 60), "evening": (12 * 60, 27 * 60), "night": (NIGHT_START, 27 * 60)}
CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_PART = r"(ونص|ونصف|وربع|الا ربع|إلا ربع)"
SPOKEN = re.compile(rf"(?:الساعة|الساعه)\s*(\d{{1,2}})(?!\d|:)(?:\s*{_PART})?"
                    rf"|(?<!\d|:)(\d{{1,2}})\s*{_PART}?\s*{TIME_WORDS}")
TIME_WITH_WORD = re.compile(rf"(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*{_PART}?\s*({TIME_WORDS})")
# formal time words are الصباح / الظهر / العصر / المساء (decisions_v3 rule 11)
# (after midnight is «الليل» in both registers: «12 الليل», «1 الليل», «2 الليل», 00:00-03:00, rule 35 and
# decisions_v16; batch 10 gen-00933 «من 7 الصباح إلى 1 الليل»)
FORMAL_CASUAL_TIME = re.compile(r"\d\s*(?:ونص\s*|وربع\s*)?(?:الصبح|المسا(?!ء))"
                                r"|(?<!\d)(?!(?:12|1|2)(?!\d))\d{1,2}\s*(?:ونص\s*|وربع\s*)?(?:الليل|بالليل)")
FORMAL_BANNED = ["يا قلبي", "حبيبتي"]
BANNED_PHRASES = ["ننطرك", "عال العال", "تأكد لي", "بيواصلونك", "يواصلونك",  # rules 5, 16, 17
                  "طال عمرك", "طويل العمر", "تبقين على راسنا"]  # rules 19, 22
# rule 23: emojis only ✅ on a done booking or cancellation, 🌹 / 🌸 answering thanks, at most one per message
ALLOWED_EMOJI, FLOWERS = {"✅", "🌹", "🌸"}, {"🌹", "🌸"}
EMOJI_PARTS = {"‍", "️", "♀", "♂"}  # joiners and modifiers inside one emoji
DONE_WORD = re.compile(rf"(?<![{AR}])تم(?![{AR}])")  # «تم», not «تمام»
THANKS = re.compile(r"شكر|مشكور|العافي|تسلم|يسلمو|جزاك|ما قصرت|كفيت ووفيت|الله يسعدك|الله يخليك")
# rule 24: «الله يعافيك، العفو» repeats the reply; «ولو» does not answer thanks
THANKS_REPLY_OLW = re.compile(rf"^\W*ولو(?![{AR}])")
# a courtesy answer with nothing to answer: «الله يعافيك» / «الله يحييك» opening a reply to a plain request (batch 02)
# rule 27: «الله يعافيك» anywhere in a reply needs a courtesy from the customer just before (missed mid-reply in
# 00378, 00438, 00526: «تم إلغاء الحجز. الله يعافيك، وإذا حبيت…»)
COURTESY_ANSWER = re.compile(r"(الله يعافيك)")
# replies say times the spoken way: «3 ونص المساء», not «15:30» (batch 06 gen-00573)
CLOCK_24 = re.compile(r"(?<!\d)(1[3-9]|2[0-3]|00):([0-5]\d)(?!\d)")
# a lone digit at the end of a customer line that no time word asks for («التعامل ٥», batch 06 gen-00574)
STRAY_DIGIT = re.compile(r"(\S+)\s+[0-9٠-٩]\W*$")
NUMBER_TAKERS = re.compile(rf"^(?:و?(?:الساعة|الساعه|او|أو|ولا|بعد|قبل|لين|الى|إلى|من|لي|يعني|حوالي|حول|تقريبا|عددنا|احنا|حنا|نحن)"
                           rf"|و?(?:{_DAY})|و?(?:{_REL}))$")
# rule 29: «الله يحييك» answers «حياك» only, never thanks or a plain request, anywhere in the reply (batch 03)
YAHYIK = re.compile(r"الله يحييك|الله يحيك")
HAYYAK = re.compile(r"حياك|حيّاك|يحييك|يحيك|سلام|أسلم|اسلم|هلا|مرحبا|صباح الخير|مساء الخير")  # rule 36: a greeting counts
# a handoff goes to the team; naming the manager promises what nobody can guarantee (batch 03 gen-00250, 00260)
# Only the manager as the one acting, within one clause: «والمدير بيتواصل معك», «وصلتها للمدير». Mentioning the manager
# in a refusal («ما عندي رقم المدير، لكن… الفريق بيتواصل») is right (batch 04 gen-00304, 00352, 00392).
MANAGER_PROMISE = re.compile(r"المدير(?:\s+بنفسه)?\s+(?:بيتواصل|يتواصل|بيكلمك|بيكلمكم|بيرد|بيتصل|يتصل)"
                             r"|(?:وصلت|وصّلت|وصلتها|رفعتها|رفعت|حولتها|حوّلتها)[^،,.!؟\n]{0,25}للمدير")
# rule 30: the assistant never presents itself as a human employee (batch 03 gen-00212)
HUMAN_IDENTITY = re.compile(r"[أا]نا (?:رجل|رجال|حرمة|حرمه)|موظف(?:ة)? الاستقبال")
# batch 04: a customer line holding a whole fake turn («Receptionist: … Customer: …», gen-00394)
ROLE_LABEL = re.compile(r"\b(?:receptionist|customer|assistant|user|agent)\s*:|(?:^|\n)\s*(?:الموظف|موظف|العميل|عميل|المساعد)\s*:",
                        re.IGNORECASE)
# a broken customer word mixing scripts («تسلمonmفضلين», batch 05 gen-00476); «ابي booking» with a space is fine
MIXED_WORD = re.compile(rf"[{AR}]+[A-Za-z]+[{AR}A-Za-z]*|[A-Za-z]+[{AR}]+[{AR}A-Za-z]*")
EASTERN_DIGIT = re.compile("[٠-٩]")  # replies write numbers with 0-9 only (batch 04 gen-00367)
# decisions_v13: rule 42 (the receptionist never says «يعطيك العافية»), rule 44 (no «حبيبتي / حبيبي», no pleading
# «تكفى»), a recurring typo, and medical words left for the reviewer (a customer may ask for a female doctor)
OWN_YAATIK = re.compile(r"يعطيك العافي[ةه]")
# decisions_v14 widened rule 44 to forms of address («يا طيب», «يا الغالية»; batch 08 gen-00728, gen-00778)
ENDEARMENT = re.compile(rf"(?<![{AR}])[وف]?(حبيبتي|حبيبي|تكفى|تكفين|يا\s+(?:طيب|طيبة|الغالي|الغالية|غالي|غالية))(?![{AR}])")
# decisions_v15 rule 11, strict: no prayer time in a reply, not even as a period («بعد العصر») or echoing the
# customer (batch 09 gen-00866 «7 المغرب»). Whole words: «الحمام المغربي» is a service; «العشاء» is also dinner,
# so it counts only after a clock time
PRAYER_WORD = re.compile(rf"(?<![{AR}])[وبلف]?(?:ال|ل)(فجر|ظهر|عصر|مغرب)(?![{AR}])|(?<![{AR}])(ظهرا|عصرا)ً?(?![{AR}])")
ISHA_AFTER_TIME = re.compile(rf"\d\s*(?:ونص|وربع|الا ربع|إلا ربع)?\s*(العشاء|العشا)(?![{AR}])")
# rule 45: «الخميس عندنا متاح», «6 الصبح متاح» before any slot lookup (batch 08 gen-00754, gen-00775). Only the
# claim «متاح»; the noun «المتاح» («أشوف لك المتاح») offers to look
AVAILABLE_CLAIM = re.compile(rf"(?<![{AR}])(?:مو\s+|مب\s+)?متاح(?:ة|ين)?(?![{AR}])")
TYPOS = ["إجانتنا", "اجانتنا"]
MEDICAL_WORDS = re.compile(r"دكتور|طبيب|مختص")
# rule 35: a business closing at midnight says «لين 12 الليل», not «12 المساء» (noon) (batch 04 gen-00344)
NOON_FOR_MIDNIGHT = re.compile(r"(?:إلى|الى|لين|لـ|حتى|ل)\s*12\s*(?:المساء|المسا)(?![ء-ي])")
COURTESY_CALL = re.compile(r"العافي|يعافيك|حياك|حيّاك|يحييك|شكر|مشكور|تسلم|يسلمو|جزاك|ما قصرت|كفيت ووفيت|الله يسعدك|الله يخليك")
# the customer's «ابشر» is answered «الله يبشرك بالخير», not «أبشر» (rule 21; batch 02 gen-00188)
CUSTOMER_ABSHIR = re.compile(rf"(?<![{AR}])[أا]بشر(?![{AR}])")
REPLY_ABSHIR = re.compile(rf"^\W*و?[أا]بشر(?![{AR}])")
# «الملغي» for «الإلغاء» and «ألغى» for the first-person «ألغي» (batch 01); «الحجز الملغي» is fine
CANCEL_WORDING = re.compile(rf"(?<![{AR}])و?(ألغى|الغى)(?![{AR}])|(?<!الحجز )(?<!الموعد )(?<![{AR}])(الملغي)(?![{AR}])")
CUSTOMER_FORMAL = ["في انتظار"]  # with MSA_WORDS, on customer lines (batch 01 gen-00045)
# rule 18: Modern Standard Arabic duals; Saudi says «حجزين», «موعدين»
MSA_DUALS = ["حجزان", "موعدان", "وقتان", "يومان", "ساعتان", "خياران", "شخصان", "خدمتان", "جلستان", "حصتان",
             "طاولتان", "قاعتان", "غرفتان", "فرعان"]
MSA_DUAL_RE = re.compile(rf"(?<![{AR}])[وبل]?({'|'.join(MSA_DUALS)})(?![{AR}])")
# masculine forms addressed to the customer, rejected at a women-only business (pilot_v3 gen-00000)
MASCULINE = ["عطني", "تبي", "تبغى", "تحب", "تقدر", "تامر", "تآمر", "أبشر", "ابشر", "تفضل", "خبرني", "اختار",
             "ارسل", "أرسل", "تكفى", "حاب", "متأكد"]
MASCULINE_RE = re.compile(rf"(?<![{AR}])[وف]?({'|'.join(MASCULINE)})(?![{AR}])")
# after the customer gives a woman's name, the same forms are wrong anywhere («تبقى» was written for «تبغى»)
MASCULINE_AFTER_NAME_RE = re.compile(rf"(?<![{AR}])[وف]?({'|'.join(MASCULINE + ['تبقى'])})(?![{AR}])")
# the teacher's own reasoning leaking into a reply (pilot_v3 gen-00010, gen-00029)
URL = re.compile(r"https?://\S+|\S+\.(?:com|sa|net)\S*")
ENGLISH_SENTENCE = re.compile(r"[A-Za-z']+(?:[\s,;:!?-]+[A-Za-z']+){3,}")
SELF_TALK = re.compile(r"\b(?:Hmm+|Alternative|Let me|I should|I need to|I will|tool result|the user|system prompt)\b"
                       r"|ما أبدأ|التعليمات|القواعد|البرومبت|نتيجة الأداة", re.IGNORECASE)
SALAAM = re.compile(r"(?:ال)?سلام عليكم")
RETURNED_SALAAM = re.compile(r"^\W*وعليكم السلام")
ABSHIR_ASK = re.compile(r"[أا]بشر\s+ب(?:اسم|عنوان|رقم|جوال)")  # rule 14: «ابشر باسمك» meaning "give me your name"
HEALTH_TIP = re.compile(r"اشرب|مويه|موية|الشمس|ارتاح|كمادات|مسكن|بنادول|ثلج")  # rule 15; crude, so a flag
FEMININE = ["أبشري", "ابشري", "تفضلي", "حبيبتي", "يا غالية", "يا الغالية", "عزيزتي", "تبين", "تبغين", "تحبين",
            "تقدرين", "عطيني", "ارسلي", "تسلمين", "اختاري", "تحجزين", "حبيتي", "احتجتي", "تختارين", "تكونين",
            "تقولين", "تحتاجين", "تشوفين", "تامرين", "تآمرين", "تفضلين"]
# whole words only: «تبيني ألغيه» and «تعطيني» are masculine, but contain «تبين» and «عطيني»
FEMININE_RE = re.compile(rf"(?<![{AR}])و?(" + "|".join(FEMININE) + rf")(?![{AR}])")
# other 2nd-person feminine verbs («تحجزين»), minus nouns of the same shape: too crude to reject on, so a flag
FEMININE_SHAPE = re.compile(rf"(?<![{AR}])و?(ت[{AR}]{{2,5}}ين)(?![{AR}])")
NOT_FEMININE = {"تمرين", "تحسين", "تعيين", "تزيين", "تخزين", "تدوين", "تأمين", "تكوين", "تلوين", "تسخين", "تموين",
                "تبيين", "تنظيفين", "تمارين"}
# a clause that states opening hours («نقفل 6 المسا») may use them even while slots are offered
HOURS_WORDS = re.compile(r"فتحنا|نفتح|نقفل|نسكر|يفتح|يقفل|يسكر|تفتح|تقفل|تسكر|مفتوح|فاتح|دوام|يوقف|نبدأ|يبدأ|نخلص")
# Evidence that the customer is a woman comes only from what she says about herself: her name or a
# feminine word about herself, as whole words (in pilot_v2 «وعد» matched inside «موعد»). Words she
# addresses to the receptionist («تكفين») say nothing about her.
FEMALE_NAME = re.compile(rf"(?<![{AR}])(?:{'|'.join(n.replace('ة', '[ةه]') for n in CUSTOMER_NAMES['female'])})(?![{AR}])")
# feminine adjectives a customer uses about herself («ماني متاكده», «حابه أسأل»). With ه some read as a man
# plus «it» («حابه» = "I like it", «محتاجه» = "I need it"), so those count only with ة or before a verb.
FEMALE_SELF_WORDS = ["متأكد", "متاكد", "مستعجل", "فاضي", "مشغول", "تعبان", "جاي"]
FEMALE_SELF_TA = ["حاب", "محتاج", "ناوي", "حاجز", "مرتبط"]
FEMALE_SELF = re.compile(rf"(?:انا|أنا|ماني|مانيب)\s+(?:(?!ب|ال|في)[{AR}]+ة(?![{AR}])|حامل)"
                         rf"|(?<![{AR}])(?:{'|'.join(w + '[ةه]' for w in FEMALE_SELF_WORDS)})(?![{AR}])"
                         rf"|(?<![{AR}])(?:{'|'.join(FEMALE_SELF_TA)})(?:ة(?![{AR}])|ه\s+[أا])"
                         rf"|(?<![{AR}])و?(?:زوجي|صديقاتي|ربيعاتي)(?![{AR}])")
# «وأتابع لك» if the wait runs long is accepted (decisions_v2: «إن تأخر عليك الوضع»), so it is not here.
AFTER_HANDOFF_PROMISE = ["ثواني", "بأرد", "برد عليك", "أرد لك", "ارد لك", "بجيك", "برجع لك", "أعلمك", "اعلمك",
                         "أبلغك", "ابلغك"]
CLAIM_VERBS = ["سجلت", "سجّلت", "واصلت", "بلغتهم", "أكدت لهم", "اكدت لهم", "رفعت", "حدثت", "عدلت", "أرسلت لك",
               "ارسلت لك"]
# «محجوز لك» claims a booking; «كله محجوز» (fully booked) does not
BOOKED_CLAIM = re.compile(r"محجوز(?:ة)?\s+(?:لك|باسمك|لكم)|حجزت لك|حجزتلك")
HANDOFF_VERBS = ["حولت", "حوّلت"]
HANDOFF_CLAIMS = {"رفعت", "بلغتهم", "واصلت"}  # «سؤالك رفعته للفريق» after handoff_to_human
# «وصلت ملاحظتك للفريق»: says something reached the team; only true in a turn that called handoff_to_human
# (batch 02: details added after the first handoff were said to have reached the team)
_SENT = rf"(?<![{AR}])[وف]?(?:وصل|وصّل|وضح|وضّح|رفع|بلغ|نقل|أرسل|ارسل|حولت|حوّلت|حولنا|حوّلنا)[{AR}]*"
_TEAM = rf"(?<![{AR}])(?:لل|ل)(?:فريق|إدارة|ادارة)[{AR}]*"
TEAM_CLAIM = re.compile(rf"{_SENT}[^،,.!؟\n]*{_TEAM}|{_TEAM}[^،,.!؟\n]*{_SENT}")
# rule 43 / complaints: promising to pass it on («بحولك للفريق») in a turn that called no handoff (Stage 7 test:
# the tuned model said it would hand off complaints without the tool call, a habit from the training data)
_WILL_SEND = rf"(?<![{AR}])[وف]?(?:بحو?ّ?ل|أحو?ّ?ل|احو?ّ?ل|بنحو?ّ?ل|برفع|أرفع|ارفع|بنرفع|بوصل|بوصّل)[{AR}]*"
# an offer («أقدر أحول طلبك للفريق», «تبيني أحوله؟») is not a promise
_OFFER = r"(?<!أقدر )(?<!اقدر )(?<!تبيني )(?<!تبغاني )(?<!تبغيني )(?<!ودك )(?<!تبي )"
# «بقول لهم إنك تبي تعويض» with no tool call (batch 08 gen-00723): telling the team is a handoff too
_WILL_TELL = rf"(?<![{AR}])[وف]?(?:بقول|بأقول|بنقول|ببلغ|ببلّغ|بنبلغ|بخبر|بنخبر)"
HANDOFF_PROMISE = re.compile(rf"{_OFFER}{_WILL_SEND}[^،,.!؟\n]*{_TEAM}|{_OFFER}{_WILL_SEND}(?=\s*(?:لهم|للمسؤول))"
                             rf"|{_OFFER}{_WILL_TELL}(?:هم(?![{AR}])|(?=\s*(?:لهم|للمسؤول))|[^،,.!؟\n]*{_TEAM})")
# rule 25: «لا تتأخرون علي» is not answered «الله يعينك»
HURRY = re.compile(r"تتأخر|تتاخر|بسرعه|بسرعة|استعجل|مستعجل|ضروري|عاجل")
PLACEHOLDER_NAMES = {"غير معروف", "غير محدد", "عميل", "العميل", "unknown", "customer", "n/a", "-", "؟", "?", ""}
ENGLISH_PHRASE = re.compile(r"[A-Za-z]+[\s,]+[A-Za-z]+")


def text_times(text: str) -> set[tuple[int, int]]:
    """(hour, minute) for every time written in a reply: 16:30, الساعة 4 ونص, 4 ونص العصر, 9 الا ربع."""
    t = text.translate(AR_DIGITS)
    out = {(int(h), int(m)) for h, m in CLOCK.findall(t)}
    t = CLOCK.sub(" ", t)
    for h1, part1, h2, part2 in SPOKEN.findall(t):
        h, part = int(h1 or h2), part1 or part2
        out.add(spoken_time(h, 0, part))
    return out


def spoken_time(h: int, m: int, part: str) -> tuple[int, int]:
    if part in ("الا ربع", "إلا ربع"):
        return ((h - 1) % 12 or 12, 45)
    return (h, {"ونص": 30, "ونصف": 30, "وربع": 15}.get(part, m))


def clock12(h: int, m: int) -> tuple[int, int]:
    return (h % 12 or 12, m)


def match_date(m: re.Match, n: int, today: date) -> date | None:
    """The date a DATE_RE-style match names (the next one, for a date without a year); None if impossible."""
    g = m.groupdict()
    if g.get(f"y{n}"):
        y, month, d = int(g[f"y{n}"]), int(g[f"iso_m{n}"]), int(g[f"iso_d{n}"])
    else:
        d = int(g[f"d{n}"])
        month = int(g[f"m{n}"]) if g.get(f"m{n}") else MONTHS[g[f"mon{n}"]]
        y = today.year + (1 if month < today.month - 6 else 0)
    try:
        return date(y, month, d)
    except ValueError:
        return None


def day_problems(text: str, today: date) -> list[str]:
    """Day names next to «اليوم / بكرة / بعد بكرة» or a date (in any format) must agree with the clock."""
    t = text.translate(AR_DIGITS)
    out = []
    # Only «relative day, then weekday» (بكرة السبت). The reverse order is ambiguous:
    # «السبت بعد بكره كذلك» means "Saturday, like the day after tomorrow" (pilot gen-00028).
    for rel, day in REL_THEN_DAY.findall(t):
        expected = (today + timedelta(days=RELATIVE[rel])).weekday()
        if WEEKDAY[day] != expected:
            out.append(f"«{rel}» called «{day}», but it is {WEEKDAYS_AR[expected]}")
    for regex, n in ((DAY_THEN_DATE, 1), (DATE_THEN_DAY, 2)):
        for m in regex.finditer(t):
            real = match_date(m, n, today)
            if real is None:
                out.append(f"impossible date «{m.group(0)}»")
            elif WEEKDAY[m.group("day")] != real.weekday():
                out.append(f"{real:%d/%m} called «{m.group('day')}», but it is {WEEKDAYS_AR[real.weekday()]}")
    return list(dict.fromkeys(out))


def dated_times(msgs: list[dict]) -> dict[date, set[tuple[int, int]]]:
    """Times the tools gave for each date: offered slots, existing bookings, booked times."""
    out: dict[date, set] = {}

    def add(d, t):
        try:
            out.setdefault(date.fromisoformat(d), set()).add(clock12(*map(int, t.split(":"))))
        except (TypeError, ValueError, AttributeError):
            pass
    for m in msgs:
        if m["role"] == "tool":
            try:
                res = json.loads(m["content"])
            except ValueError:
                continue
            for t in res.get("slots") or []:
                add(res.get("date"), t)
            for b in res.get("bookings") or []:
                add(b.get("date"), b.get("time"))
        for tc in m.get("tool_calls") or []:
            a = tc["function"]["arguments"]
            if isinstance(a, dict) and a.get("date") and a.get("time"):
                add(a["date"], a["time"])
    return out


def day_slot_problems(text: str, today: date, dated: dict, extra: set) -> list[str]:
    """A time said right after a day must be one the tools gave for that day (pilot_v2 gen-00019:
    Thursday's only slot was 12:00, the reply said «بكرة الخميس 12 ونص», and 12:30 was a Saturday slot).
    A time just before the next day name may belong to that day, so both count. Days the tools
    never looked at are not checked here."""
    t = text.translate(AR_DIGITS)
    refs = []  # (start, end, candidate dates)
    for m in re.finditer(rf"(?<!\S)[وبل]{{0,2}}({_REL})(?![{AR}])", t):
        refs.append((m.start(), m.end(), {today + timedelta(days=RELATIVE[m.group(1)])}))
    for m in re.finditer(rf"(?<![{AR}])[وبل]?({_DAY})(?![{AR}])", t):
        refs.append((m.start(), m.end(), {d for d in dated if d.weekday() == WEEKDAY[m.group(1)]}))
    for m in DATE_RE.finditer(t):
        d = match_date(m, 0, today)
        refs.append((m.start(), m.end(), {d} if d else set()))
    refs.sort(key=lambda r: r[0])
    # a day name and a relative day written side by side are one reference («بكرة الخميس»); in
    # «السبت بعد بكره كذلك» (an accepted slip, decisions_v2) they disagree, so either day counts
    merged: list = []
    for start, end, cands in refs:
        if merged and not re.search(r"\d", t[merged[-1][1]:start]) and len(t[merged[-1][1]:start].strip()) <= 10:
            merged[-1] = (merged[-1][0], end, merged[-1][2] | cands)
        else:
            merged.append((start, end, cands))
    refs = merged
    out = []
    for k, (_, end, cands) in enumerate(refs):
        nxt = refs[k + 1] if k + 1 < len(refs) else None
        seen = [d for d in cands if d in dated]
        if not seen:
            continue
        here = set().union(*(dated[d] for d in seen), extra)
        after = set().union(*(dated.get(d, set()) for d in (nxt[2] if nxt else ())))
        # a day's times end with its sentence; only the clause right before the next day name may
        # hold that day's times
        raw = t[end:nxt[0] if nxt else len(t)]
        stop = re.search(r"[.!؟]", raw)
        *head, tail = re.split(r"[،,\n]", raw[:stop.start()] if stop else raw)
        wrong = ({clock12(*x) for x in text_times(" ".join(head))} - here) | \
                ({clock12(*x) for x in text_times(tail)} - here - (set() if stop else after))
        for h, mm in sorted(wrong):
            out.append(f"{h}:{mm:02d} is not a slot on {', '.join(f'{d:%a %d/%m}' for d in sorted(seen))}")
    return list(dict.fromkeys(out))


def emojis_in(text: str) -> list[str]:
    return [c for c in EMOJI.findall(text) if c not in EMOJI_PARTS]


def emoji_fits(e: str, text: str, last_user: str) -> bool:
    """Rule 23: ✅ on a message saying something is done («تم»), a flower answering thanks."""
    return (e == "✅" and bool(DONE_WORD.search(text))) or (e in FLOWERS and bool(THANKS.search(last_user)))


def emoji_problems(text: str, last_user: str) -> list[str]:
    ems = emojis_in(text)
    out = []
    if set(ems) - ALLOWED_EMOJI:
        out.append("emoji not allowed: " + " ".join(sorted(set(ems) - ALLOWED_EMOJI)))
    if len(ems) > 1:
        out.append(f"{len(ems)} emojis in one message (at most one)")
    out += [f"{e} in the wrong place" for e in dict.fromkeys(ems) if e in ALLOWED_EMOJI and not emoji_fits(e, text, last_user)]
    return out


def repair_emojis(text: str, last_user: str, switch_on: bool) -> str:
    """Remove every emoji rule 23 does not allow, and the space it leaves; nothing else changes.
    Keeps the first allowed emoji that fits its message, if the switch is on."""
    keep = next((e for e in emojis_in(text) if switch_on and e in ALLOWED_EMOJI and emoji_fits(e, text, last_user)), None)
    out, kept, i = [], False, 0
    while i < len(text):
        c = text[i]
        if not EMOJI.match(c):
            out.append(c)
            i += 1
            continue
        if c == keep and not kept:
            kept = True
            out.append(c)
            i += 1
            continue
        i += 1
        nxt = text[i] if i < len(text) else "\n"
        if EMOJI.match(nxt):  # the rest of the same emoji, or another one: handled next
            continue
        if out and out[-1] == " " and nxt in " \n،,.!؟؛:":
            out.pop()  # «حياك الله 🌿» -> «حياك الله», «حياك الله 🌿، وش» -> «حياك الله، وش»
            # between two clauses on one line the emoji was the separator: «حياك 🌸 عندك» -> «حياك، عندك»
            after = text[i + 1] if nxt == " " and i + 1 < len(text) else ""
            if out and out[-1].isalnum() and after.isalnum():
                out.append("،")
        elif (not out or out[-1] == "\n") and nxt == " ":
            i += 1  # «🌿 حياك الله» at the start of a line
    return "".join(out)


def time_word_problems(text: str, known24: dict, hours24: dict, by_customer: frozenset = frozenset()) -> tuple[list[str], list[str]]:
    """A time-of-day word must fit the hour it names (decisions_v4 rule 11: morning before 12:00,
    evening from 12:00, casual «الليل» late; «الظهر» and «العصر» are not time labels). The hour comes
    from the tools when the time is one of theirs (so «12 المساء» for a 12:00 slot is noon, not
    midnight); in a sentence that states opening hours («من 8 الصبح لين 8 المسا») the opening hours
    count too. A time the customer said with the same word («احجز لي 8 المساء» → «ما عندنا 8 المساء») is theirs,
    not the tools'. Returns (problems, flags): «الليل» up to NIGHT_TOLERANCE before NIGHT_START is a flag."""
    bad, near = [], []
    found = []
    for sentence in re.split(r"[.!؟\n]", text.translate(AR_DIGITS)):
        lookup = {k: known24.get(k, set()) | hours24.get(k, set()) for k in known24.keys() | hours24.keys()} \
            if HOURS_WORDS.search(sentence) else known24
        found += [(x, lookup) for x in TIME_WITH_WORD.findall(sentence)]
    for (h, mm, part, word), lookup in found:
        h, m = spoken_time(int(h), int(mm or 0), part)
        if h > 24 or m > 59:
            continue
        said = f"«{h}{':%02d' % m if m else ''} {word}»"
        kind = TIME_KIND[word]
        if kind not in TIME_WINDOWS:  # «الظهر / العصر»: PRAYER_WORD rejects them anywhere (rule 11, strict)
            continue
        cands = {h * 60 + m} if h > 12 else lookup.get(clock12(h, m)) or {h % 12 * 60 + m, (h % 12 + 12) * 60 + m}
        # the customer's own time («8 المساء» while a tool lists 08:00) is read the customer's way, but the word
        # must still fit one reading of the hour: «7 الليل» (07:00 or 19:00) never does (decisions_v17,
        # rescued gen-00190 echoed the customer's «٧ بالليل»)
        if (clock12(h, m), kind) in by_customer:
            cands = {h * 60 + m} if h > 12 else {h % 12 * 60 + m, (h % 12 + 12) * 60 + m}
        start, end = TIME_WINDOWS[kind]

        def fits(before: int) -> bool:
            return any(start - before <= x < end for t in cands for x in (t, t + 1440))
        hhmm = "/".join(f"{t // 60:02d}:{t % 60:02d}" for t in sorted(cands))
        window = f"{start // 60:02d}:{start % 60:02d}-{end // 60 % 24:02d}:{end % 60:02d}"
        if fits(0):
            continue
        if kind == "night" and fits(NIGHT_TOLERANCE):
            near.append(f"time word near a boundary: {said} for {hhmm} ({word} is {window})")
        else:
            bad.append(f"time word does not fit the hour: {said} for {hhmm} ({word} is {window})")
    return bad, near


def labelled_only(text: str, t: tuple[int, int], these: set[int], others: set[int]) -> bool:
    """Whether the reply labels the 12-hour time t with a word that fits one of `these` hours (minutes
    of the day) and none of `others`: «7 الصباح» is the 07:00 slot, «7 المساء» the 19:00 one."""
    def fits(kind: str, mins: set[int]) -> bool:
        start, end = TIME_WINDOWS[kind]
        return any(start <= x < end for m in mins for x in (m, m + 1440))
    for h, mm, part, word in TIME_WITH_WORD.findall(text.translate(AR_DIGITS)):
        kind = TIME_KIND[word]
        if clock12(*spoken_time(int(h), int(mm or 0), part)) == t and kind in TIME_WINDOWS \
                and fits(kind, these) and not fits(kind, others):
            return True
    return False


# ... said of a time or a day. «الاثنين» is also "both" («الكاش ومدى، والاثنين متاحين», batch 09 gen-00890),
# so it counts as Monday only after «يوم» or a relative day
_DAYS_NOT_MONDAY = "|".join(d for d in sorted(WEEKDAY, key=len, reverse=True) if "ثنين" not in d)
AVAILABLE_WHEN = re.compile(rf"\d|(?<![{AR}])[وبل]?(?:{_DAYS_NOT_MONDAY}|{_REL})(?![{AR}])"
                            rf"|(?:يوم|{_REL})\s+(?:ال)?[اإ]?ثنين(?![{AR}])")
HOUR_WORDS = {"وحده": 1, "واحد": 1, "ثنتين": 2, "اثنين": 2, "ثلاث": 3, "اربع": 4, "أربع": 4, "خمس": 5, "ست": 6,
              "سبع": 7, "ثمان": 8, "ثمني": 8, "تسع": 9, "عشر": 10, "احدعش": 11, "حدعش": 11, "اثنعش": 12, "ثنعش": 12}
HOUR_WORD_RE = re.compile(rf"(?<![{AR}])(?:ال)?({'|'.join(sorted(HOUR_WORDS, key=len, reverse=True))})(?![{AR}])")
CONFIRM = re.compile(rf"(?<![{AR}])(?:إيه|ايه|اي|إي|ايوه|إيوه|نعم|أكيد|اكيد|تمام|اوكي|أوكي|[أا]لغ[ِ]?يه|[أا]لغ[ِ]?ه)(?![{AR}])")
ALL_OF_THEM = re.compile(r"كلهم|كلها|الاثنين|الثنين|الحجزين|الموعدين|الثنتين")
GENERIC_SERVICE_WORDS = {"حصه", "جلسه", "موعد", "حجز"}


def norm_word(w: str) -> str:
    w = re.sub(r"[ً-ْ]", "", w).translate(str.maketrans("أإآة", "اااه"))
    return w[2:] if w.startswith("ال") and len(w) > 4 else w


def cancel_unnamed(msgs: list[dict], i: int, booking_id: str) -> bool:
    """Rule 46: a cancel_booking (in message i) is fine only when the customer's last message names that
    booking (its service, day or date, or «كلهم»), or confirms the receptionist's question about it, or
    the customer only ever had that one booking. A repeated «إيه، الغيه» after a done cancellation
    named nothing (batch 08 gen-00751 then cancelled the other booking)."""
    bookings = {}
    for m in msgs[:i]:
        if m["role"] == "tool" and m.get("name") == "get_my_bookings":
            try:
                bookings.update({b["booking_id"]: b for b in json.loads(m["content"]).get("bookings") or []})
            except (ValueError, KeyError, TypeError):
                pass
    b = bookings.get(booking_id)
    users = [k for k in range(i) if msgs[k]["role"] == "user"]
    # an id the tools never showed is the invented-id check's business; with one booking there is no wrong
    # one to cancel (a reschedule done as cancel + create, after the customer gives a name, is fine)
    if b is None or not users or len(bookings) == 1:
        return False
    last_user = msgs[users[-1]]["content"]
    t = last_user.translate(AR_DIGITS)
    words = {norm_word(w) for w in re.findall(rf"[{AR}]+", t)}
    named = {norm_word(w) for w in re.findall(rf"[{AR}]+", b.get("service", ""))}
    named = {w for w in named if len(w) >= 3} - GENERIC_SERVICE_WORDS
    try:
        d = date.fromisoformat(b["date"])
        named |= {norm_word(WEEKDAYS_AR[d.weekday()])}
        # its date or its hour («ألغِ الأول حق ٨ المساء», train_v1 gen-00358)
        hour = int(str(b.get("time", "0:0")).split(":")[0])
        day_said = bool({str(d.day), str(hour % 12 or 12)} & set(re.findall(r"\d+", t)))
    except (KeyError, ValueError):
        day_said = False
    if booking_id in last_user or ALL_OF_THEM.search(last_user) or words & named or day_said:
        return False
    asked = next((msgs[k]["content"] for k in range(users[-1] - 1, -1, -1)
                  if msgs[k]["role"] == "assistant" and msgs[k].get("content")), "")
    return not (CONFIRM.search(last_user) and "؟" in asked)


def rule_checks(rec: dict, business: dict) -> tuple[list[str], list[str]]:
    """The native-review rules as automatic checks. Returns (problems that reject, flags)."""
    meta, msgs = rec["meta"], rec["messages"]
    today = datetime.fromisoformat(meta["now"]).date()
    formal = meta["style"]["register"] == "formal"
    problems, flags = [], []
    hours = {clock12(int(x) // 60, int(x) % 60) for spec in business["schedule"].values() if spec
             for x in (to_min(p) for p in spec.split("-"))}
    # the real hour of each time on a 12-hour clock: the tools' times first, then opening hours
    # (a gym closing at 24:00 must not turn a 12:00 slot into midnight)
    known24: dict[tuple[int, int], set[int]] = {}
    for x in [int(h) * 60 + int(mm) for m in msgs if m["role"] == "tool" or m.get("tool_calls")
              for h, mm in CLOCK.findall(m.get("content") or json.dumps([tc["function"]["arguments"] for tc in m.get("tool_calls") or []]))]:
        known24.setdefault(clock12(x // 60 % 24, x % 60), set()).add(x % 1440)
    hours24: dict[tuple[int, int], set[int]] = {}
    for x in [to_min(p) for spec in business["schedule"].values() if spec for p in spec.split("-")]:
        hours24.setdefault(clock12(x // 60 % 24, x % 60), set()).add(x % 1440)
    for k, v in hours24.items():
        known24.setdefault(k, v)
    dated = dated_times(msgs)
    services = " ".join(s["name"] for s in business["services"])
    allowed_tool, allowed_customer, women = set(), set(), business["customers"] == "women only"
    after_times: set[tuple[int, int]] = set()  # the `after` of each slot search, down to the half hour
    handoff_done, booked, first_reply, first_user, last_user = False, False, True, None, ""
    named_woman = False  # the customer gave a woman's name
    customer_said = set()  # (time, word kind) the customer wrote, e.g. «8 المساء»
    closes_midnight = any(spec and spec.split("-")[1] in ("24:00", "00:00") for spec in business["schedule"].values())
    # slots the tools listed for today that have already passed (the backend lists the whole day)
    now = datetime.fromisoformat(meta["now"])
    now_min = now.hour * 60 + now.minute
    # 12-hour time -> minutes of the day; today's 07:00 (past) and 19:00 (to come) share «7» (train_v1 gen-00780)
    past_today, later_today, other_days = {}, {}, set()
    for m in msgs:
        if m["role"] == "tool" and m.get("name") == "get_available_slots":
            try:
                res = json.loads(m["content"])
            except ValueError:
                continue
            for t in res.get("slots") or []:
                if res.get("date") == str(today):
                    side = past_today if to_min(t) < now_min else later_today
                    side.setdefault(clock12(*map(int, t.split(":"))), set()).add(to_min(t))
                else:
                    other_days.add(clock12(*map(int, t.split(":"))))
    for i, m in enumerate(msgs):
        if m["role"] == "user":
            text = m["content"]
            allowed_customer |= {clock12(h, mm) for h, mm in text_times(text)}
            allowed_customer |= {clock12(int(n), 0) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", text.translate(AR_DIGITS))
                                 if 1 <= int(n) <= 24}
            # an hour written as a word («مثلا ست الصباح», batch 11 gen-01010; «الساعه عشر», batch 10 gen-00914)
            allowed_customer |= {(HOUR_WORDS[w], 0) for w in HOUR_WORD_RE.findall(text)}
            in_digits = HOUR_WORD_RE.sub(lambda x: str(HOUR_WORDS[x.group(1)]), text).translate(AR_DIGITS)
            for h, mm, part, word in TIME_WITH_WORD.findall(in_digits):
                customer_said.add((clock12(*spoken_time(int(h), int(mm or 0), part)), TIME_KIND[word]))
            if FEMALE_NAME.search(text) or FEMALE_SELF.search(text):
                women = True
            if FEMALE_NAME.search(text):
                named_woman = True
            for h, mm, part, word in TIME_WITH_WORD.findall(text.translate(AR_DIGITS)):
                customer_said.add((clock12(*spoken_time(int(h), int(mm or 0), part)), TIME_KIND[word]))
            stray = STRAY_DIGIT.search(text.strip())
            if stray and not NUMBER_TAKERS.match(stray.group(1)):
                problems.append(f"stray digit at the end of a customer line: «…{stray.group(0)}»")
            if MIXED_WORD.search(text):
                problems.append(f"Latin letters inside an Arabic word in a customer line: «{MIXED_WORD.search(text).group(0)}»")
            if ROLE_LABEL.search(text):
                problems.append(f"role label in a customer line: «{ROLE_LABEL.search(text).group(0).strip()}»")
            if any(int(h) == 0 for h, *_ in TIME_WITH_WORD.findall(text.translate(AR_DIGITS))):
                problems.append("impossible time «0 …» in a customer line")
            if ENGLISH_PHRASE.search(text):
                problems.append(f"English phrase in a customer line: «{text[:40]}»")
            problems += [f"formal word in a customer line «{w.strip()}»" for w in MSA_WORDS + CUSTOMER_FORMAL if w in text]
            # rule 12: only the customer's first message may greet
            if first_user is not None and RETURNED_SALAAM.search(text):
                problems.append("customer starts a later message with «وعليكم السلام»")
            first_user = text if first_user is None else first_user
            last_user = text
            continue
        if m["role"] == "tool" or m.get("tool_calls"):
            texts = [m["content"]] if m["role"] == "tool" else [json.dumps(tc["function"]["arguments"]) for tc in m["tool_calls"]]
            for tx in texts:
                allowed_tool |= {clock12(int(h), int(mm)) for h, mm in CLOCK.findall(tx)}
            if m.get("tool_calls") and any(tc["function"]["name"] == "handoff_to_human" for tc in m["tool_calls"]):
                handoff_done = True
            if m["role"] == "tool" and m.get("name") in ("create_booking", "reschedule_booking") and '"confirmed"' in m["content"]:
                booked = True
            for tc in m.get("tool_calls") or []:
                a = tc["function"]["arguments"]
                # «بعد 3 ونص المسا» for a search after 15:42: the after time, down to the half hour (rule 11, strict)
                if isinstance(a, dict) and CLOCK.fullmatch(str(a.get("after", ""))):
                    after_min = to_min(a["after"]) // 30 * 30
                    allowed_tool.add(clock12(after_min // 60, after_min % 60))
                    after_times.add(clock12(after_min // 60, after_min % 60))
                if tc["function"]["name"] == "cancel_booking" and isinstance(a, dict) and \
                        cancel_unnamed(msgs, i, str(a.get("booking_id", ""))):
                    problems.append(f"cancels {a.get('booking_id')}, which the customer did not name or confirm (rule 46)")
                if tc["function"]["name"] == "create_booking" and isinstance(a, dict) and \
                        str(a.get("customer_name", "")).strip().lower() in PLACEHOLDER_NAMES:
                    problems.append(f"create_booking with a placeholder name «{a.get('customer_name', '')}»")
                if tc["function"]["name"] in ("create_booking", "reschedule_booking") and isinstance(a, dict) and \
                        a.get("date") == str(today) and CLOCK.fullmatch(str(a.get("time", ""))) and to_min(a["time"]) < now_min:
                    problems.append(f"books {a['time']} today, already past (now {now:%H:%M})")
            continue
        text = m.get("content") or ""
        if not text:
            continue
        # tools called since the customer's last message, and whether a slot list is among them
        turn = list(itertools.takewhile(lambda x: x["role"] != "user", reversed(msgs[:i])))
        slots_now = any(x["role"] == "tool" and x.get("name") == "get_available_slots" for x in turn)
        acted_now = any(x.get("tool_calls") for x in turn)
        # 1a + rule 11: formal register
        if formal and first_reply and "هلا" in text:
            problems.append("formal row opens with «هلا»")
        if formal:
            problems += [f"formal reply says «{w}»" for w in FORMAL_BANNED if w in text]
            if FORMAL_CASUAL_TIME.search(text.translate(AR_DIGITS)):
                problems.append("formal reply uses casual time words (formal: الصباح / المساء)")
        # rule 13: return the salaam in the first reply, and only there
        if first_reply and first_user and SALAAM.search(first_user) and "عليكم السلام" not in text:
            problems.append("does not return the customer's «السلام عليكم»")
        if not first_reply and RETURNED_SALAAM.search(text) and not SALAAM.search(last_user):
            problems.append("a later reply opens with «وعليكم السلام» again")
        # 1b: times match a tool time exactly (minutes included); when slots were just offered,
        # opening hours count only in a sentence that states them («دوامنا يبدأ 2 المساء بالخميس، و4 المساء بباقي الأيام»)
        stated = {clock12(*t) for c in re.split(r"[.!؟\n]", text) if HOURS_WORDS.search(c) for t in text_times(c)}
        allowed = allowed_tool | allowed_customer | ((stated & hours) if slots_now else hours)
        bad_times = sorted({clock12(*t) for t in text_times(text)} - allowed)
        if bad_times:
            problems.append("time not from a tool: " + ", ".join(f"{h}:{mm:02d}" for h, mm in bad_times))
        problems += day_slot_problems(text, today, dated, allowed_customer | (stated & hours) | after_times)
        # a slot already past today, offered (pilot_v3 gen-00048: 13:00-17:00 offered at 18:31)
        passed = sorted(t for t in ({clock12(*t) for t in text_times(text)} & past_today.keys()) - other_days - allowed_customer
                        if t not in later_today or labelled_only(text, t, past_today[t], later_today[t]))
        if passed:
            problems.append("offers a time already past today: " + ", ".join(f"{h}:{mm:02d}" for h, mm in passed)
                            + f" (now {now:%H:%M})")
        # rule 11: the time-of-day word fits the hour
        bad_words, near_words = time_word_problems(text, known24, hours24, frozenset(customer_said))
        problems += bad_words
        flags += near_words
        # 1c: day names and dates agree with the clock; dates are written the way people say them
        problems += day_problems(text, today)
        if ISO_DATE.search(text.translate(AR_DIGITS)):
            problems.append("ISO date (2027-01-05) in a reply")
        # 1d, 1e, rule 14: loose ends and banned phrases
        if "..." in text or "…" in text:
            problems.append("reply contains «...»")
        problems += [f"banned phrase «{w}»" for w in BANNED_PHRASES if w in text]
        if ABSHIR_ASK.search(text):
            problems.append(f"«{ABSHIR_ASK.search(text).group(0)}» used to ask for something (say «عطني»)")
        if "الكشف" in text and "كشف" not in services:
            problems.append("«الكشف» at a business with no such service")
        dual = MSA_DUAL_RE.search(text)
        if dual:
            problems.append(f"Modern Standard Arabic dual «{dual.group(1)}» (Saudi: «حجزين», «موعدين»)")
        # the teacher's reasoning leaking into the reply
        plain = URL.sub(" ", text)
        if ENGLISH_SENTENCE.search(plain):
            problems.append(f"English sentence in a reply: «{ENGLISH_SENTENCE.search(plain).group(0)[:40]}»")
        if SELF_TALK.search(plain):
            problems.append(f"self-talk in a reply: «{SELF_TALK.search(plain).group(0)}»")
        # masculine forms to the customer at a women-only business (pilot_v3 gen-00000)
        masc = MASCULINE_RE.search(text)
        if business["customers"] == "women only" and masc:
            problems.append(f"masculine form «{masc.group(1)}» at a women-only business")
        # ... and after the customer gave a woman's name (batch 01 gen-00092)
        masc = MASCULINE_AFTER_NAME_RE.search(text)
        if named_woman and business["customers"] != "women only" and masc:
            problems.append(f"masculine form «{masc.group(1)}» after the customer gave a woman's name")
        # rule 23: emojis
        problems += emoji_problems(text, last_user)
        # rule 24: courtesy pairs
        if "يعافيك" in text and "العفو" in text:
            problems.append("«الله يعافيك» and «العفو» in one reply")
        if THANKS.search(last_user) and THANKS_REPLY_OLW.search(text):
            problems.append("«ولو» as a reply to thanks")
        courtesy = COURTESY_ANSWER.search(text)
        if courtesy and not COURTESY_CALL.search(last_user):
            problems.append(f"«{courtesy.group(1)}» but the customer said no «يعطيك العافية», «حياك» or thanks")
        if YAHYIK.search(text) and not HAYYAK.search(last_user):
            problems.append("«الله يحييك» but the customer did not say «حياك» (rule 29)")
        if MANAGER_PROMISE.search(text):
            problems.append(f"promises the manager: «{MANAGER_PROMISE.search(text).group(0)[:30]}»")
        if HUMAN_IDENTITY.search(text):
            problems.append(f"presents itself as a person: «{HUMAN_IDENTITY.search(text).group(0)}» (rule 30)")
        if OWN_YAATIK.search(text):
            problems.append("the receptionist says «يعطيك العافية» (rule 42)")
        if ENDEARMENT.search(text):
            problems.append(f"«{ENDEARMENT.search(text).group(1)}» in a reply (rule 44)")
        prayer = PRAYER_WORD.search(text) or ISHA_AFTER_TIME.search(text.translate(AR_DIGITS))
        if prayer:
            problems.append(f"prayer time «{prayer.group(0).strip()}» in a reply (rule 11: clock times only)")
        # rule 45: availability of a day or time claimed before any slot lookup
        if not any(x["role"] == "tool" and x.get("name") == "get_available_slots" for x in msgs[:i]):
            claim45 = next((s for s in re.split(r"[.!؟\n]", text.translate(AR_DIGITS)) if AVAILABLE_CLAIM.search(s)
                            and AVAILABLE_WHEN.search(s)), None)
            if claim45:
                problems.append(f"says «{AVAILABLE_CLAIM.search(claim45).group(0)}» before any slot lookup (rule 45)")
        problems += [f"typo «{w}»" for w in TYPOS if w in text]
        if MEDICAL_WORDS.search(text):
            flags.append(f"medical word «{MEDICAL_WORDS.search(text).group(0)}» (rule 43: check it is not advice)")
        if CLOCK_24.search(text):
            problems.append(f"24-hour time «{CLOCK_24.search(text).group(0)}» in a reply (say «3 ونص المساء»)")
        if EASTERN_DIGIT.search(text):
            problems.append("digits ٠-٩ in a reply (replies use 0-9)")
        if closes_midnight and NOON_FOR_MIDNIGHT.search(text):
            problems.append("«12 المساء» for a midnight closing (say «12 الليل», rule 35)")
        if CUSTOMER_ABSHIR.search(last_user) and REPLY_ABSHIR.search(text):
            problems.append("the customer's «ابشر» answered «أبشر» (say «الله يبشرك بالخير»)")
        # «الملغي» for «الإلغاء», «ألغى» for «ألغي» (batch 01)
        cancel = CANCEL_WORDING.search(text)
        if cancel:
            problems.append(f"«{cancel.group(1) or cancel.group(2)}» (say «ألغي» / «الإلغاء»)")
        # rule 15: health or care tips (a word list cannot tell them from practical tips)
        if HEALTH_TIP.search(text):
            flags.append(f"possible health tip «{HEALTH_TIP.search(text).group(0)}»")
        # rule 34 (relaxed, decisions_v15): one option per line is only the teacher's default; slot lists will be
        # laid out outside the model, so options in one line are neither flagged nor repaired
        # 1f: feminine forms need evidence first
        fem = FEMININE_RE.search(text)
        if not women and fem:
            problems.append(f"feminine form «{fem.group(1)}» before any sign the customer is a woman")
        elif not women:
            shape = next((w for w in FEMININE_SHAPE.findall(text) if w not in NOT_FEMININE), None)
            if shape:
                flags.append(f"possible feminine form «{shape}»")
        # rule 7: after a handoff, the team replies, not the receptionist
        if handoff_done and any(w in text for w in AFTER_HANDOFF_PROMISE):
            problems.append(f"after a handoff, promises to reply itself («{next(w for w in AFTER_HANDOFF_PROMISE if w in text)}»)")
        # rule 10: claims an action no tool did in this turn, or a booking before any booking tool
        claim = next((w for w in CLAIM_VERBS if w in text), None)
        # passing something to the team is true once a handoff happened, even in an earlier turn
        if claim and not acted_now and not (claim in HANDOFF_CLAIMS and handoff_done):
            problems.append(f"claims «{claim}» with no tool call")
        if BOOKED_CLAIM.search(text) and not booked:
            problems.append(f"says «{BOOKED_CLAIM.search(text).group(0)}» before any booking tool")
        if any(w in text for w in HANDOFF_VERBS) and not handoff_done:
            problems.append("says it transferred the request, but there was no handoff")
        # «وصلت ... للفريق» needs a handoff_to_human call in this turn (a detail added later is not sent)
        handoff_now = any(tc["function"]["name"] == "handoff_to_human" for x in turn for tc in x.get("tool_calls") or [])
        team = TEAM_CLAIM.search(text)
        if team and not handoff_now:
            problems.append(f"says «{team.group(0)[:30]}» but this turn sent nothing to the team")
        promise = HANDOFF_PROMISE.search(text)
        if promise and re.match(r"[^.!؟\n]*؟", text[promise.start():]):  # a question offers, it does not promise
            promise = None
        if promise and not handoff_now:
            problems.append(f"promises «{promise.group(0)[:30]}» without calling handoff_to_human in this turn")
        # rule 25
        if "الله يعينك" in text and HURRY.search(last_user):
            problems.append("«الله يعينك» as a reply to a request to hurry")
        first_reply = False
    problems += unsaid_closed_days(msgs, today, business) + move_direction_problems(msgs, today)
    return list(dict.fromkeys(problems + address_problems(rec, business))), list(dict.fromkeys(flags))


def train_tools(tools: list[dict]) -> list[dict]:
    """The training copy of the tools: create_booking gets an optional `address` for home visits.
    spec/tools.json stays as it is, so the frozen test set and the Stage 5 baselines are unchanged."""
    out = json.loads(json.dumps(tools))
    params = next(t for t in out if t["function"]["name"] == "create_booking")["function"]["parameters"]
    params["properties"]["address"] = {"type": "string", "description": "District and street, only for home visits"}
    return out


class TrainBackend(Backend):
    """The test backend, plus the optional address on create_booking (training only)."""

    def create_booking(self, service_id: str, date: str, time: str, customer_name: str, address: str | None = None) -> dict:
        result = super().create_booking(service_id, date, time, customer_name)
        if address and "booking_id" in result:
            self.bookings[result["booking_id"]]["address"] = address
        return result


def address_problems(rec: dict, business: dict) -> list[str]:
    """Home-visit bookings must carry the customer's address."""
    if "home visit" not in business["type"]:
        return []
    return ["home-visit booking without an address" for m in rec["messages"] for tc in m.get("tool_calls") or []
            if tc["function"]["name"] == "create_booking" and isinstance(tc["function"]["arguments"], dict)
            and not str(tc["function"]["arguments"].get("address", "")).strip()]


def opener(rec: dict) -> str:
    """How the first receptionist reply opens, for the per-run opener mix (1g)."""
    first = next((m["content"] for m in rec["messages"] if m["role"] == "assistant" and m.get("content")), "")
    text = re.sub(r"^وعليكم السلام[^،,.!\s]*(?: ورحمة الله(?: وبركاته)?)?[،,.!\s]*", "", first.strip())
    for o in ["هلا والله", "يا هلا", "هلا", "أهلين", "اهلين", "أهلا", "اهلا", "حياك الله", "حياك", "مرحبا", "يا مرحبا",
              "أبشر", "ابشر", "تم"]:
        if text.startswith(o):
            return o
    return "other"


def closing(rec: dict) -> str:
    """Which courtesy closing the last receptionist reply uses, for the per-run closing mix."""
    last = next((m["content"] for m in reversed(rec["messages"]) if m["role"] == "assistant" and m.get("content")), "")
    return next((c for c in sorted(CLOSINGS, key=len, reverse=True) if c in last), "other / none")


def run_report(kept: list[dict], rejected: list[dict]) -> str:
    """Per-run summary: formal pass rate, rejections per check, the opener mix (1g) and the closing mix
    of the kept conversations."""
    from collections import Counter

    gen = [r for r in kept + rejected if "messages" in r]
    formal = [r for r in gen if r["meta"]["style"]["register"] == "formal"]
    formal_kept = [r for r in kept if r["meta"]["style"]["register"] == "formal"]
    reasons = Counter(re.sub(r"«[^»]*»|\d[\d:/., ]*", "…", p) for r in rejected for p in r.get("problems", []))
    openers = Counter(opener(r) for r in gen)
    lines = [f"kept {len(kept)} of {len(gen)} generated; formal rows kept {len(formal_kept)} of {len(formal)}",
             "rejections by check (a conversation can fail several):"]
    lines += [f"  {n:3d}  {reason}" for reason, n in reasons.most_common()]
    lines.append("first-reply openers: " + ", ".join(f"{o} {n}" for o, n in openers.most_common()))
    lines.append("closings (kept): " + ", ".join(f"{c} {n}" for c, n in Counter(closing(r) for r in kept).most_common()))
    return "\n".join(lines)


def leak_score(line: str, test_grams: list) -> float:
    """Highest 3-gram overlap with any test/dev customer line. Lines under 5 words («السلام عليكم ورحمة الله»)
    are greetings and small talk that every conversation shares, not leaked test content, so they score 0;
    so does the full salaam «السلام عليكم ورحمة الله وبركاته» (5 words, batch 05 gen-00447, gen-00486)."""
    if len(line.split()) < 5 or re.fullmatch(r"\W*(?:ال)?سلام عليكم(?:\s+ورحم[ةه] الله(?:\s+وبركات[هة])?)?\W*", line):
        return 0.0
    g = trigrams(line)
    return max((jaccard(g, t) for t in test_grams), default=0.0)


CLOSED_WORDS = re.compile(r"مغلق|مسكر|مقفل|مقفول|سكرين|قفلين|[إا]جاز[ةه]|إجازتنا|اجازتنا|عطل[ةه]|ما نفتح|مو فاتحين"
                          r"|ما نشتغل|ما عندنا دوام|ما فيه دوام")


def plain_ar(text: str) -> str:
    return re.sub(r"[ً-ْ]", "", text)  # without harakat and shadda («مقفّلين» → «مقفلين»)


def named_days(text: str, today: date) -> list[date]:
    """The dates a customer line names: «اليوم / بكرة / بعد بكرة» and weekday names (the next such day)."""
    t = plain_ar(text)
    out = [today + timedelta(days=RELATIVE[m.group(1)]) for m in re.finditer(rf"(?<![{AR}])[وبل]?({_REL})(?![{AR}])", t)]
    for m in re.finditer(rf"(?<![{AR}])[وبل]?({_DAY})(?![{AR}])", t):
        out.append(today + timedelta(days=(WEEKDAY[m.group(1)] - today.weekday()) % 7))
    return out


EXISTING_BOOKING = re.compile(r"عندي (?:موعد|حجز)|موعدي|حجزي|موعدنا|حجزنا")
# rule 47 is about asking for that day: to book, or whether it is open («كيف الجو عندكم اليوم؟» on a closed Friday
# is small talk, batch 12 gen-01175)
BOOK_INTENT = re.compile(r"احجز|حجز|موعد|متاح|فاضي|فاتحين|تفتحون|مفتوحين|دوام|اوقات|أوقات|وقت|ينفع|يمديكم|تجون")


def unsaid_closed_days(msgs: list[dict], today: date, business: dict) -> list[str]:
    """Rule 47 (decisions_v17): when the customer asks for a day the business is closed, the reply says it is
    closed before offering other days (batch 11 gen-01059, batch 09 gen-00840). Once said, later replies need
    not repeat it."""
    said, out = False, []
    for i, m in enumerate(msgs):
        if m["role"] == "assistant" and m.get("content") and CLOSED_WORDS.search(plain_ar(m["content"])):
            said = True
        # a line about an existing booking («عندي موعد اليوم», «ابي احول موعدي من بكرة لبعد بكرة») is not a request
        # for that day: rule 39 (check the booking's real date first) comes before rule 47 (gen-01015, gen-00885)
        if m["role"] != "user" or said or EXISTING_BOOKING.search(m["content"]) or not BOOK_INTENT.search(m["content"]):
            continue
        closed = [d for d in named_days(m["content"], today) if open_hours(business, d) is None]
        if not closed:
            continue
        reply = None
        for x in msgs[i + 1:]:
            if x["role"] == "user":
                break
            if x["role"] == "assistant" and x.get("content"):
                reply = x["content"]
                break
        if reply is not None and not CLOSED_WORDS.search(plain_ar(reply)):
            out.append(f"the customer asked for {WEEKDAYS_AR[closed[0].weekday()]} {closed[0]:%d/%m}, a closed day, "
                       f"and the reply does not say it is closed (rule 47)")
    return out


# «نأخره للاثنين» / «نقدمه لبكرة»: the direction word followed by the day it moves to. «لا تتأخر» (be late) and
# «نقدم لك» (we offer) have no «ل + day» after them
MOVE = re.compile(rf"(?<![{AR}])(?P<verb>[نتأ]أخر|[نت]اخر|أأخر|[نتأ]قدم)(?:ه|ها|هم)?\s+(?:موعدك\s+|حجزك\s+)?(?:ل|لـ|إلى|الى)"
                  rf"(?P<rest>[^.،؟!\n]*)")


def move_direction_problems(msgs: list[dict], today: date) -> list[str]:
    """«نأخر / تأخر» moves a booking later and «نقدم / تقدم» earlier (rule 41's wording; batch 11 rescued
    gen-00830 and batch 06 gen-00588 said «نأخره» for an earlier day)."""
    from scoring import dates_in
    bookings: list[date] = []
    out = []
    for m in msgs:
        if m["role"] == "tool" and m.get("name") == "get_my_bookings":
            try:
                bookings += [date.fromisoformat(b["date"]) for b in json.loads(m["content"]).get("bookings") or []]
            except (ValueError, KeyError, TypeError):
                pass
        if m["role"] != "assistant" or not m.get("content") or not bookings:
            continue
        text = plain_ar(m["content"]).translate(AR_DIGITS)
        for mv in MOVE.finditer(text):
            rest = "ل" + mv.group("rest")
            target = [d for d in (date(today.year + (1 if mo < today.month - 6 else 0), mo, dd)
                                  for dd, mo in dates_in(rest) if 1 <= dd <= 31) if d] or named_days(rest, today)[:1]
            mentioned = [b for b in bookings if (b.day, b.month) in dates_in(text)]
            old = mentioned[0] if mentioned else (bookings[0] if len(set(bookings)) == 1 else None)
            if not target or old is None or target[0] == old:
                continue
            later = "خر" in mv.group("verb")
            if later and target[0] < old:
                out.append(f"«{mv.group('verb')}» (later) moves {old:%d/%m} to the earlier {target[0]:%d/%m}: say «نقدمه»")
            elif not later and target[0] > old:
                out.append(f"«{mv.group('verb')}» (earlier) moves {old:%d/%m} to the later {target[0]:%d/%m}: say «نأخره»")
    return out


def closed_day_dates_ok(problems: list[str], text: str, business: dict, now: datetime) -> list[str]:
    """The benchmark's date check (scoring.py, frozen) accepts only dates a tool or the customer gave. For training,
    the date of a closed day is fine in a sentence that says it is closed («بعد بكرة الجمعة 19 مارس، وإحنا الجمعة
    مغلقين», decisions_v16): no tool looks up a closed day."""
    from scoring import dates_in
    out = []
    for p in problems:
        if p.startswith("dates ") and "match no real date" in p:
            wrong = [tuple(int(x) for x in t) for t in re.findall(r"\((\d+), (\d+)\)", p)]
            sentences = [s for s in re.split(r"[.!؟\n]", text) if CLOSED_WORDS.search(s)]
            said_closed = {dm for s in sentences for dm in dates_in(s)}
            left = []
            for d, mo in wrong:
                y = now.year + (1 if mo < now.month - 6 else 0)
                try:
                    closed = open_hours(business, date(y, mo, d)) is None
                except ValueError:
                    closed = False
                if not (closed and (d, mo) in said_closed):
                    left.append((d, mo))
            if left:
                out.append(p if len(left) == len(wrong) else f"dates {left} match no real date in the conversation")
            continue
        out.append(p)
    return out


def check(rec: dict, spec: tuple, tok, test_grams: list) -> list[str]:
    """Every reason this conversation must not be used for training (empty = keep)."""
    businesses, styles, tools = spec
    b = businesses[rec["meta"]["business_id"]]
    meta = rec["meta"]
    now = datetime.fromisoformat(meta["now"])
    short = build_system_prompt(b, styles, meta["style"], now, meta["prayer_times"], "short")
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    problems = []
    for i, m in enumerate(rec["messages"]):
        if m["role"] == "tool" and '"error"' in m["content"]:
            problems.append(f"tool error: {m['content'][:60]}")
        if m["role"] == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                issues = validity({"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}, schemas)
                problems += [f"invalid call {tc['function']['name']}: {x}" for x in issues]
        if m["role"] == "assistant" and m.get("content"):
            text = m["content"]
            problems += closed_day_dates_ok(reply_problems(text, Context(short, rec["messages"][:i])), text, b, now)
            problems += [f"formal word {w!r}" for w in MSA_WORDS if w in text]
            if LATIN_WORD.search(text):
                problems.append("Arabizi")
            if meta["style"]["emoji"] == "off" and EMOJI.search(text):
                problems.append("emoji while the switch is off")
            hour = now.hour
            if ("صباح الخير" in text and hour >= 12) or ("مساء الخير" in text and hour < 12):
                problems.append("greeting does not fit the time")
        if m["role"] == "user":
            best = leak_score(m["content"], test_grams)
            if best >= 0.6:
                problems.append(f"customer line too close to a test/dev line ({best:.2f})")
    rule_problems, rule_flags = rule_checks(rec, b)
    problems += rule_problems
    # Flags go to the native-speaker review instead of rejecting: word lists are too crude
    # to judge dialect on their own.
    replies = " ".join(m["content"] for m in rec["messages"] if m["role"] == "assistant" and m.get("content"))
    rec["flags"] = list(rule_flags)
    if len(replies.split()) >= 12 and sum(w in replies for w in SAUDI_WORDS) < 2:
        rec["flags"].append("few Saudi marker words")
    msgs = [{"role": "system", "content": short}] + rec["messages"]
    order = [next(t for t in tools if t["function"]["name"] == n) for n in meta["tools"]]
    n_tokens = len(tok.apply_chat_template(msgs, tools=order, tokenize=True, return_dict=True)["input_ids"])
    rec["n_tokens"] = n_tokens  # length is recorded, not rejected: Stage 7 sets the limit
    if n_tokens > TOKEN_LIMIT:
        rec["flags"].append(f"{n_tokens} tokens (over {TOKEN_LIMIT})")
    return problems


def cmd_generate(args) -> None:
    from transformers import AutoTokenizer

    businesses = json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))
    _, styles, tools = load_spec()
    tools = train_tools(tools)
    spec_list = (businesses, styles, tools)
    spec_by_id = ({b["id"]: b for b in businesses}, styles, tools)
    EXAMPLES.update({reg: voho_examples(reg) for reg in ("formal", "casual")})
    tok = AutoTokenizer.from_pretrained("google/gemma-4-12B-it")
    test_grams = [trigrams(m["content"]) for f in ("test_v1.jsonl", "dev_v1.jsonl")
                  for l in (ROOT / "data" / "test" / f).read_text(encoding="utf-8").splitlines()
                  for m in json.loads(l)["messages"] if m["role"] == "user"]
    teacher = OpenRouterModel(args.teacher)
    rng = random.Random(args.seed)
    scenarios = [sample_scenario(rng, businesses) for _ in range(args.n)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keep_path, reject_path = OUT_DIR / f"{args.out}.jsonl", OUT_DIR / f"{args.out}.rejects.jsonl"
    done = {json.loads(l)["id"] for p in (keep_path, reject_path) if p.exists()
            for l in p.read_text(encoding="utf-8").splitlines()}
    state = {"spent": 0.0, "kept": 0, "rejected": 0, "stop": False}

    def work(item):
        idx, sc = item
        if state["stop"] or f"gen-{idx:05d}" in done:
            return
        rec, problems, spent = generate_one(idx, sc, teacher, spec_list)
        if rec is not None:
            repair_record(rec)
            problems = check(rec, spec_by_id, tok, test_grams)
        with LOCK:
            state["spent"] += spent
            if rec is None:
                rec = {"id": f"gen-{idx:05d}", "scenario": sc["kind"], "meta": {"business_id": sc["business"]["id"]}}
            path = reject_path if problems else keep_path
            if problems:
                rec["problems"] = problems
                state["rejected"] += 1
            else:
                state["kept"] += 1
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{rec['id']} {sc['kind']:10s} {'REJECT ' + problems[0][:70] if problems else 'kept'} "
                  f"(${state['spent']:.3f})", flush=True)
            if state["spent"] >= args.budget:
                state["stop"] = True
                print(f"Budget ${args.budget:.2f} reached: stopping. Re-run to continue.")

    # The scenario list depends only on the seed and --n, so batch k is always the same 100 scenarios
    # and an interrupted batch resumes where it stopped.
    items = list(enumerate(scenarios))[batch_range(args.batch)] if args.batch else list(enumerate(scenarios))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, items))
    print(f"\ncost ${state['spent']:.3f} this run")
    read = lambda p: [r for l in p.read_text(encoding="utf-8").splitlines() if in_batch(r := json.loads(l), args.batch)] \
        if p.exists() else []
    print(run_report(read(keep_path), read(reject_path)))


def cmd_recheck(args) -> None:
    """Re-apply the current checks to every generated conversation of a run (kept or rejected)."""
    from transformers import AutoTokenizer

    businesses = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
    _, styles, tools = load_spec()
    tools = train_tools(tools)
    tok = AutoTokenizer.from_pretrained("google/gemma-4-12B-it")
    test_grams = [trigrams(m["content"]) for f in ("test_v1.jsonl", "dev_v1.jsonl")
                  for l in (ROOT / "data" / "test" / f).read_text(encoding="utf-8").splitlines()
                  for m in json.loads(l)["messages"] if m["role"] == "user"]
    keep_path, reject_path = OUT_DIR / f"{args.name}.jsonl", OUT_DIR / f"{args.name}.rejects.jsonl"
    read = lambda p: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    kept, rejected = [], []
    for was_kept, r in sorted([(True, r) for r in read(keep_path)] + [(False, r) for r in read(reject_path)],
                              key=lambda x: x[1]["id"]):
        if not in_batch(r, args.batch):  # other batches stay exactly as they are
            (kept if was_kept else rejected).append(r)
            continue
        r.pop("problems", None)
        r.pop("flags", None)
        if "messages" in r:
            repair_record(r)
        problems = check(r, (businesses, styles, tools), tok, test_grams) if "messages" in r else ["generation failed"]
        (rejected if problems else kept).append({**r, **({"problems": problems} if problems else {})})
    for path, rows in ((keep_path, kept), (reject_path, rejected)):
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(run_report([r for r in kept if in_batch(r, args.batch)], [r for r in rejected if in_batch(r, args.batch)]))


def render(rec: dict) -> str:
    lines = []
    for m in rec["messages"]:
        if m["role"] == "user":
            lines.append(f"عميل: {m['content']}")
        elif m.get("tool_calls"):
            lines += [f"[أداة] {tc['function']['name']}({json.dumps(tc['function']['arguments'], ensure_ascii=False)})"
                      for tc in m["tool_calls"]]
        elif m["role"] == "tool":
            lines.append(f"[نتيجة] {m['content'][:120]}")
        else:
            lines.append(f"موظف: {m['content']}")
    return "\n".join(lines)


# Rule 34: 3 or more options go one per line. The repair splits only lines that clearly offer options: a lead-in
# ending in «:» that names options (المتاح، الأوقات، عندنا…), or a line whose items are all times. Booking
# summaries («حصة يوغا، السبت 20 مارس، 7 ونص، ورقم حجزك…») are not options and stay as they are.
LIST_LEAD = re.compile(r"متاح|الأوقات|أوقات|الاوقات|اوقات|المواعيد|مواعيد|عندنا|الخدمات|خدمات|الخيارات|خيارات|فاضي|فاضية|تختار")
LIST_LEAD_SPLIT = re.compile(r"^(.*?[^\d\s]\s*:)\s*(.*)$")  # «المتاح: …», not the colon inside «10:30»


DATE_WORDS = re.compile(rf"{_DAY}|{_REL}|{_MON}")
ONLY_TIME = re.compile(rf"^\d{{1,2}}(?::\d{{2}})?(?:\s*{_PART})?(?:\s*{TIME_WORDS})?$")


def list_segments(body: str) -> list[tuple[int, int]]:
    """Spans of the parts of a sentence split at «،» / «,» outside brackets («(500 ريال، 60 دقيقة)» is one part,
    batch 07 gen-00699), and at a «و» joining two times («8 الصبح و10 الصبح و12 المسا», gen-00619)."""
    spans, depth, start = [], 0, 0
    for i, c in enumerate(body + "،"):
        depth += (c == "(") - (c == ")")
        if c in "،," and depth == 0:
            spans.append((start, i))
            start = i + 1
    out = []
    for s, e in spans:
        cuts = [m.start() for m in re.finditer(r"\s+و\s*(?=\d)", body[s:e])]
        for a, b in zip([s] + [s + c for c in cuts], [s + c for c in cuts] + [e]):
            if body[a:b].strip():  # «، و7 المسا»: the «و» right after a comma is not a second split
                out.append((a, b))
    return out


def inline_list(sentence: str) -> tuple[str, str | None, list[str], str] | None:
    """(text before the list, lead-in, items, the sentence end) if this sentence lists 3 or more options inline,
    else None. The lead-in ends with «:» or with an options word («عندنا», «متاح»…), which may come after a first
    clause («ما عندنا تفصيل ثوب، عندنا قص شعر، سشوار…», gen-00648); without one, every item must be just a time.
    A leading «و» on the 2nd and later items is dropped (no service name starts with «و»)."""
    body = sentence.strip()
    end = body[-1] if body and body[-1] in ".؟!" else ""
    body = body[:-1] if end else body
    m = LIST_LEAD_SPLIT.match(body)
    colon_lead = m.group(1).strip() if m else None
    if colon_lead:
        body = m.group(2)
    segs = list_segments(body)
    for k in range(0, len(segs) - 2):
        if colon_lead and k > 0:
            break
        prefix = body[:segs[k][0]].rstrip()
        items = [body[s:e].strip() for s, e in segs[k:]]
        lead = colon_lead
        if lead is None:  # «عندنا تنظيف مكيف، …»: the lead-in is the text up to the last options word
            words = list(LIST_LEAD.finditer(items[0]))
            negated = words and re.search(r"(?:^|\s)(?:ما|مو|مب)\s*$", items[0][:words[-1].start()])  # «ما عندنا…»
            if words and not negated and items[0][words[-1].end():].strip():
                cut = items[0].find(" ", words[-1].end())
                if cut > 0:
                    lead, items[0] = items[0][:cut].strip(), items[0][cut:].strip()
                    if any(len(x.split()) > 4 for x in items):  # without «:», only short items are options
                        continue
        if len(items) < 3 or any(not x or len(x.split()) > 6 or "رقم" in x or "B-" in x for x in items):
            continue
        if any(re.match(r"(?:أو|او|ولا)\s", x) for x in items[1:]):
            continue  # «أو» is a word, not one of the separators the founder named
        # a day, a date or «اليوم / بكرة» among the items makes it a description («كشف بيطري، الثلاثاء 26 يناير، 11
        # الصباح»), not options, unless the options are the days themselves
        if any(DATE_WORDS.search(x) for x in items) and not all(re.fullmatch(rf"و?(?:{_DAY})", x) for x in items):
            continue
        items = [items[0]] + [re.sub(r"^و\s*", "", x) for x in items[1:]]
        if not ((lead and LIST_LEAD.search(lead)) or all(ONLY_TIME.match(x) for x in items)):
            continue
        if k > 0 and not lead:  # a time list after a first clause needs a lead-in word to start it
            continue
        return prefix, lead, items, end
    return None


def repair_lists(text: str) -> str:
    """One option per line (rule 34); the sentences around a list keep their own lines."""
    out = []
    for line in text.split("\n"):
        if line.lstrip().startswith("-"):  # already a bulleted line
            out.append(line)
            continue
        sentences = re.split(r"(?<=[.؟!])\s+", line)
        pending = []
        for s in sentences:
            found = inline_list(s)
            if not found:
                pending.append(s)
                continue
            if pending:
                out.append(" ".join(pending))
                pending = []
            prefix, lead, items, end = found
            out += ([prefix] if prefix else []) + ([lead] if lead else []) + items[:-1] + [items[-1] + end]
        if pending:
            out.append(" ".join(pending))
    return "\n".join(out)


def repair_record(rec: dict) -> bool:
    """The rule 23 emoji repair on one conversation, before its checks (founder decision after batch 02):
    remove every emoji the rule does not allow from the replies, and mark the conversation."""
    last_user, changed = "", False
    for m in rec["messages"]:
        if m["role"] == "user":
            last_user = m["content"]
        elif m["role"] == "assistant" and m.get("content"):
            new = repair_emojis(m["content"], last_user, rec["meta"]["style"]["emoji"] == "on")
            changed |= new != m["content"]
            m["content"] = new
    if changed:
        rec["repairs"] = sorted(set(rec.get("repairs", [])) | {"emoji"})
    # rule 24, tightened (decisions_v16): «العفو، الله يعافيك» → «الله يعافيك»
    courtesy = False
    for m in rec["messages"]:
        if m["role"] == "assistant" and m.get("content"):
            new = repair_courtesy(m["content"])
            courtesy |= new != m["content"]
            m["content"] = new
    if courtesy:
        rec["repairs"] = sorted(set(rec.get("repairs", [])) | {"courtesy"})
    return changed or courtesy


AFW_DROP = re.compile(r"(?<![ء-ي])العفو،\s*|،\s*العفو(?![ء-ي])")


def repair_courtesy(text: str) -> str:
    """Drop «العفو،» or «، العفو» from a reply that also says «الله يعافيك», and nothing else. Any other
    «العفو» («العفو يا مشاري، الله يعافيك») is left for the checks to reject."""
    if "الله يعافيك" not in text or "العفو" not in text:
        return text
    new = AFW_DROP.sub("", text, count=1)
    return new if "العفو" not in new else text


def cmd_repair_emojis(args) -> None:
    """Rule 23 repair on kept conversations: remove every emoji the rule does not allow from the replies,
    mechanically. Checks that the text without emojis (and without the «،» put in a removed separator's
    place) is unchanged, and marks each changed conversation."""
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    plain = lambda t: re.sub(r"\s+", " ", EMOJI.sub("", t).replace("،", "")).strip()
    changed = 0
    for r in recs:
        last_user, before = "", json.dumps(r["messages"], ensure_ascii=False)
        for m in r["messages"]:
            if m["role"] == "user":
                last_user = m["content"]
            elif m["role"] == "assistant" and m.get("content"):
                new = repair_emojis(m["content"], last_user, r["meta"]["style"]["emoji"] == "on")
                if plain(new) != plain(m["content"]):
                    sys.exit(f"{r['id']}: the repair changed more than emojis")
                m["content"] = new
        if json.dumps(r["messages"], ensure_ascii=False) != before:
            changed += 1
            r["repairs"] = sorted(set(r.get("repairs", [])) | {"emoji"})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    print(f"{args.name}: {changed} of {len(recs)} conversations changed; text without emojis identical in all")


def cmd_repair_lists(args) -> None:
    """Rule 34 repair on kept conversations: 3 or more options listed in one line go one per line. Only the
    separators («،» and a leading «و») and line breaks change; that is verified for every reply.
    Retired by decisions_v15 (rule 34 relaxed): kept so the repairs already applied can be reproduced."""
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    squash = lambda t: re.sub(r"[\s،,]", "", t)
    changed_replies, changed = 0, 0
    for r in recs:
        if args.batch and not in_batch(r, args.batch):
            continue
        touched = False
        for m in r["messages"]:
            if m["role"] == "assistant" and m.get("content"):
                new = repair_lists(m["content"])
                if new == m["content"]:
                    continue
                # nothing but separators, line breaks and a leading «و» may change
                a, b = squash(m["content"]), squash(new)
                ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
                if any(op != "equal" and not (op == "delete" and set(a[i1:i2]) == {"و"}) for op, i1, i2, _, _ in ops):
                    sys.exit(f"{r['id']}: the list repair changed more than separators")
                m["content"] = new
                changed_replies += 1
                touched = True
        if touched:
            changed += 1
            r["repairs"] = sorted(set(r.get("repairs", [])) | {"list"})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    print(f"{args.name}: {changed_replies} replies in {changed} conversations put one option per line; "
          "only separators and line breaks changed")


# Rule 42: the receptionist never says «يعطيك العافية». The repair removes it with the «،», «و» or «.» that joins
# it, in three shapes; anything else (for example «يعطيك العافية يا حمد.») is left for the founder.
_YAATIK = r"(?:الله )?يعطيك العافي[ةه]"
CLOSING_SHAPES = [
    re.compile(rf"\s*[،,]\s*و?{_YAATIK}"),                              # «تم إلغاء الحجز، الله يعطيك العافية. لو…»
    re.compile(rf"(?:(?<=^)|(?<=\n)|(?<=[.!؟] )){_YAATIK}\s*[،,]\s*و?"),  # «الله يعطيك العافية، ونشوفك على خير»
    re.compile(rf"(?:\s|^){_YAATIK}\.?(?=\s*$|\n)"),                     # «…ديسمبر. الله يعطيك العافية.»
]


def repair_closing(text: str) -> str | None:
    """The reply without «يعطيك العافية», or None if it cannot be removed cleanly."""
    for shape in CLOSING_SHAPES:
        new = shape.sub("", text, count=1)
        if new != text:
            new = re.sub(r"[ \t]+\n", "\n", new).rstrip()
            if re.search(_YAATIK, new):
                new = repair_closing(new)  # a second occurrence
            return new if new and new.strip() else None
    return None


def cmd_repair_closings(args) -> None:
    """Rule 42 repair on the reviewed rows whose note asks for it: remove the receptionist's «يعطيك العافية».
    Verifies that only the phrase and its joiners («،», «و», «.», spaces) were removed."""
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    repaired, skipped = [], []
    for r in recs:
        if "closing repair (rule 42)" not in r.get("review", {}).get("note", "") or "closing" in r.get("repairs", []):
            continue
        new_msgs, ok = [], True
        for m in r["messages"]:
            if m["role"] == "assistant" and m.get("content") and re.search(_YAATIK, m["content"]):
                new = repair_closing(m["content"])
                removed = "" if new is None else "".join(
                    m["content"][i1:i2] for op, i1, i2, _, _ in difflib.SequenceMatcher(None, m["content"], new, autojunk=False).get_opcodes()
                    if op != "equal")
                if new is None or re.search(_YAATIK, new) or re.sub(rf"{_YAATIK}|[\s،,.و]", "", removed):
                    ok = False
                    break
                m = {**m, "content": new}
            new_msgs.append(m)
        if ok:
            r["messages"] = new_msgs
            r["repairs"] = sorted(set(r.get("repairs", [])) | {"closing"})
            repaired.append(r["id"])
        else:
            skipped.append(r["id"])
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    print(f"{args.name}: {len(repaired)} conversations closing-repaired; left for the founder: {skipped or 'none'}")


def spoken_clock(minutes: int, formal: bool) -> str:
    """15:30 -> «3 ونص المسا» (casual) / «3 ونص المساء» (formal); afternoon and evening times only."""
    h, m = minutes // 60, minutes % 60
    return f"{h % 12 or 12}{' ونص' if m == 30 else ''} {'المساء' if formal else 'المسا'}"


def cmd_repair_prayer_words(args) -> None:
    """Rule 11, strict (decisions_v15): in the rows a review list names, «بعد العصر» in a receptionist line
    becomes «بعد 3 ونص المسا», from the `after` of the slot search before that reply, rounded down to the
    half hour. Anything else (no `after`, another prayer word or phrase, a count that differs from the list)
    is left for the founder. Verifies that only «العصر» changed."""
    listed: dict[str, int] = {}
    rows = list(csv.DictReader(open(args.csv_path, encoding="utf-8-sig")))
    if rows and "find" in rows[0]:
        return repair_find_replace(args.name, rows)
    for row in rows:
        listed[row["id"]] = listed.get(row["id"], 0) + 1
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    repaired, skipped = [], []
    for r in recs:
        if r["id"] not in listed or "prayer word" in r.get("repairs", []):
            continue
        formal = r["meta"]["style"]["register"] == "formal"
        after, done, ok, new_msgs = None, 0, True, []
        for m in r["messages"]:
            for tc in m.get("tool_calls") or []:
                a = tc["function"]["arguments"]
                if isinstance(a, dict) and CLOCK.fullmatch(str(a.get("after", ""))):
                    after = to_min(a["after"]) // 30 * 30
            if m["role"] == "assistant" and m.get("content") and PRAYER_WORD.search(m["content"]):
                text = m["content"]
                n = len(re.findall(r"بعد العصر", text))
                if after is None or n != len(PRAYER_WORD.findall(text)) or after < 12 * 60:
                    ok = False
                    break
                clock = f"بعد {spoken_clock(after, formal)}"
                new = text.replace("بعد العصر", clock)
                # exactly reversible: only «العصر» changed, nothing else in the line
                if clock in text or new.replace(clock, "بعد العصر") != text or PRAYER_WORD.search(new):
                    ok = False
                    break
                done += n
                m = {**m, "content": new}
            new_msgs.append(m)
        # every «بعد العصر» in a listed row (the list counted 38 places; three rows had one more each)
        if ok and done >= listed[r["id"]]:
            r["messages"] = new_msgs
            r["repairs"] = sorted(set(r.get("repairs", [])) | {"prayer word"})
            repaired.append(r["id"])
        else:
            skipped.append(r["id"])
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    print(f"{args.name}: {len(repaired)} conversations prayer-word repaired; left for the founder: {skipped or 'none'}")


def repair_find_replace(name: str, rows: list[dict]) -> None:
    """Prayer-word repair, part 2 (prayer_word_repair_v2.csv): exact find → replace pairs written by the reviewer.
    Each find must occur exactly once in that row's receptionist lines; undoing the replacement must give back
    the original; afterwards no prayer word may remain in the row's replies."""
    pairs: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        pairs.setdefault(row["id"], []).append((row["find"], row["replace"]))
    path = OUT_DIR / f"{name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    repaired, skipped = [], []
    for r in recs:
        if r["id"] not in pairs or "prayer word" in r.get("repairs", []):
            continue
        msgs, ok = json.loads(json.dumps(r["messages"])), True
        for find, repl in pairs[r["id"]]:
            hits = [m for m in msgs if m["role"] == "assistant" and m.get("content") and find in m["content"]]
            if len(hits) != 1 or hits[0]["content"].count(find) != 1 or repl in hits[0]["content"]:
                ok = False
                break
            old = hits[0]["content"]
            hits[0]["content"] = old.replace(find, repl)
            if hits[0]["content"].replace(repl, find) != old:
                ok = False
                break
        if ok and any(PRAYER_WORD.search(m["content"]) for m in msgs if m["role"] == "assistant" and m.get("content")):
            ok = False
        if ok:
            r["messages"] = msgs
            r["repairs"] = sorted(set(r.get("repairs", [])) | {"prayer word"})
            repaired.append(r["id"])
        else:
            skipped.append(r["id"])
    missing = sorted(set(pairs) - {r["id"] for r in recs})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    print(f"{name}: {len(repaired)} conversations prayer-word repaired (exact pairs); "
          f"left for the founder: {skipped or 'none'}; not in this file: {missing or 'none'}")


def cmd_rescue(args) -> None:
    """Re-check rejected conversations after a rule is relaxed or a repair is added (decisions_v16): apply the
    current repairs and checks to every reject; those that now pass move to the kept file and get their own
    review sheet. Ids the founder kept rejected (--skip) stay where they are."""
    from transformers import AutoTokenizer
    businesses = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
    _, styles, tools = load_spec()
    tools = train_tools(tools)
    tok = AutoTokenizer.from_pretrained("google/gemma-4-12B-it")
    test_grams = [trigrams(m["content"]) for f in ("test_v1.jsonl", "dev_v1.jsonl")
                  for l in (ROOT / "data" / "test" / f).read_text(encoding="utf-8").splitlines()
                  for m in json.loads(l)["messages"] if m["role"] == "user"]
    keep_path, reject_path = OUT_DIR / f"{args.name}.jsonl", OUT_DIR / f"{args.name}.rejects.jsonl"
    kept = [json.loads(l) for l in keep_path.read_text(encoding="utf-8").splitlines()]
    still, rescued = [], []
    for r in (json.loads(l) for l in reject_path.read_text(encoding="utf-8").splitlines()):
        if "messages" not in r or r["id"] in args.skip:
            still.append(r)
            continue
        trial = json.loads(json.dumps(r))
        trial.pop("problems", None)
        trial.pop("flags", None)
        repair_record(trial)
        problems = check(trial, (businesses, styles, tools), tok, test_grams)
        if problems:
            still.append(r)  # unchanged: its original problems stay on record
        else:
            trial["rescued"] = args.label
            rescued.append(trial)
    kept = sorted(kept + rescued, key=lambda r: r["id"])
    keep_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8", newline="\n")
    reject_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in still), encoding="utf-8", newline="\n")
    out = OUT_DIR / f"{args.name}.rescued_{args.label}.review.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "business", "style", "scenario", "flags", "conversation", "verdict (ok / fix / bad)", "note"])
        for r in rescued:
            w.writerow([r["id"], r["meta"]["business_id"], "/".join(r["meta"]["style"].values()), r["scenario"],
                        "; ".join(sorted(f"{x} repaired" for x in r.get("repairs", [])) + r.get("flags", [])), render(r), "", ""])
    print(f"rescued {len(rescued)}: {[r['id'] for r in rescued]}; wrote {out}")


def cmd_import_review(args) -> None:
    """Attach reviewer verdicts from a filled review CSV (columns id, verdict, note) to the records.
    Only "ok" conversations are used for training; "fix" and "bad" are kept on file, not trained on."""
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    with open(args.csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    verdict_col = next(c for c in rows[0] if c.startswith("verdict"))
    verdicts = {r["id"]: (r[verdict_col].strip().lower(), r.get("note", "").strip()) for r in rows}
    unknown = [v for v, _ in verdicts.values() if v not in ("ok", "fix", "bad")]
    if unknown:
        sys.exit(f"{len(unknown)} verdicts are not ok / fix / bad, e.g. {unknown[:3]}")
    missing = [r["id"] for r in recs if r["id"] not in verdicts]
    for r in recs:
        if r["id"] in verdicts:
            v, note = verdicts[r["id"]]
            r["review"] = {"verdict": v, "note": note, "by": args.by}
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8", newline="\n")
    counts = {v: sum(1 for r in recs if r.get("review", {}).get("verdict") == v) for v in ("ok", "fix", "bad")}
    print(f"imported {sum(counts.values())} verdicts: {counts}; {len(missing)} conversations have none yet")


def batch_range(batch: int) -> slice:
    return slice((batch - 1) * BATCH_SIZE, batch * BATCH_SIZE)


def in_batch(rec: dict, batch: int | None) -> bool:
    if not batch:
        return True
    r = batch_range(batch)
    return r.start <= int(rec["id"].split("-")[-1]) < r.stop


def cmd_sheet(args) -> None:
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [r for l in path.read_text(encoding="utf-8").splitlines() if in_batch(r := json.loads(l), args.batch)]
    out = OUT_DIR / (f"{args.name}.batch{args.batch:02d}.review.csv" if args.batch else f"{args.name}.review.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "business", "style", "scenario", "flags", "conversation", "verdict (ok / fix / bad)", "note"])
        for r in recs:
            w.writerow([r["id"], r["meta"]["business_id"], "/".join(r["meta"]["style"].values()), r["scenario"],
                        "; ".join((["emoji repaired"] if "emoji" in r.get("repairs", []) else [])
                                  + (["closing repaired"] if "closing" in r.get("repairs", []) else [])
                                  + (["time-word repaired"] if "prayer word" in r.get("repairs", []) else [])
                                  + (["courtesy repaired"] if "courtesy" in r.get("repairs", []) else []) + r.get("flags", [])),
                        render(r), "", ""])
    print(f"wrote {out} ({len(recs)} conversations)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--out", required=True)
    g.add_argument("--n", type=int, required=True)
    g.add_argument("--workers", type=int, default=4)
    g.add_argument("--budget", type=float, default=0.5)
    g.add_argument("--seed", type=int, default=6)
    g.add_argument("--teacher", default=DEFAULT_TEACHER, choices=TEACHERS)
    g.add_argument("--batch", type=int, help=f"generate only batch k ({BATCH_SIZE} scenarios) of the --n scenario pool")
    s = sub.add_parser("sheet")
    s.add_argument("name")
    s.add_argument("--batch", type=int, help="only this batch of a batched run")
    ir = sub.add_parser("import-review")
    ir.add_argument("name")
    ir.add_argument("csv_path")
    ir.add_argument("--by", required=True, help="who reviewed, recorded with every verdict")
    rc = sub.add_parser("recheck")
    rc.add_argument("name")
    rc.add_argument("--batch", type=int, help="recheck only this batch; the others stay as they are")
    re_ = sub.add_parser("repair-emojis")
    re_.add_argument("name")
    rc_ = sub.add_parser("repair-closings")
    rc_.add_argument("name")
    rp = sub.add_parser("repair-prayer-words")
    rp.add_argument("name")
    rp.add_argument("csv_path")
    rs = sub.add_parser("rescue")
    rs.add_argument("name")
    rs.add_argument("--label", required=True, help="e.g. v16: names the review sheet of the rescued rows")
    rs.add_argument("--skip", nargs="*", default=[], help="ids the founder kept rejected")
    rl = sub.add_parser("repair-lists")
    rl.add_argument("name")
    rl.add_argument("--batch", type=int, help="only this batch of a batched run")
    a = ap.parse_args()
    {"generate": cmd_generate, "sheet": cmd_sheet, "recheck": cmd_recheck, "import-review": cmd_import_review,
     "repair-emojis": cmd_repair_emojis, "repair-lists": cmd_repair_lists,
     "repair-closings": cmd_repair_closings, "repair-prayer-words": cmd_repair_prayer_words,
     "rescue": cmd_rescue}[a.cmd](a)
