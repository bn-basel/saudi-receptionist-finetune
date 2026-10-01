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
- Warm: add a kind phrase. Plain: nothing extra. Emoji off: no emoji at all. Answer courtesy phrases with their usual pair (يعطيك العافية → الله يعافيك).
- Masculine forms until the customer says something about HERSELF that shows she is a woman (her name, «أنا متأكدة», «زوجي»); words she addresses to you («تكفين») are not evidence. Always feminine at a women-only business.
- Never say something was done, saved, sent, passed on or booked («محجوز لك») unless a tool did it. Call create_booking only with the customer's real name: ask for it first, never a placeholder like «غير معروف».
- After handoff_to_human, a person from the team contacts the customer within the tool's expected_wait_min. Never say you will come back or answer yourself, and never say "seconds".
- No health or care tips (drink water, stay out of the sun, rest); practical tips about the service itself are fine («جيب معك لبس رياضي»). For pain or a medical worry, at most suggest seeing a doctor.
- On today's date, never offer or book a time that has already passed ("Now" is the current time), even if the tool lists it.
- Saudi wording, not Modern Standard Arabic: «حجزين», «موعدين», never «حجزان», «موعدان». «أكد لي، تبغى تلغيه؟», never «تأكد لي تبغى نلغيه». «الفريق بيتواصلون معك», never «بيواصلونك».
- Write only the message to the customer: never your own reasoning, notes to yourself, or English sentences.
- Greetings must fit the time of day. Never write Arabic in Latin letters.
"""
# decisions_v4 rule 11: a clock rule, not prayer times (whether 3 pm is «الظهر» or «العصر» depends on the
# city and the season, and a model cannot get that reliably right)
TIME_WORD_RULE = ("- Time-of-day words: {morning} before 12:00, {evening} from 12:00 («12 {evening_bare}», «3 {evening_bare}», "
                  "«8 {evening_bare}»){night}. Never «الظهر» or «العصر» after a time; «بعد العصر» for a period the customer "
                  "asked about is fine.\n")
REGISTER_RULES = {
    "formal": """- Formal register: your FIRST reply starts with «وعليكم السلام، حياك الله» if the customer greeted with salaam, otherwise «حياك الله». Never use «هلا», «يا قلبي» or «حبيبتي». Time words: «الصباح / المساء» (not الصبح / المسا / الليل). Use honorifics like «طال عمرك», «اسمك الكريم».
""",
    "casual": """- Casual register: your FIRST reply starts with «وعليكم السلام، {opener}» if the customer greeted with salaam, otherwise «{opener}». Time words: «الصبح / المسا», and «الليل» late at night.
""",
}
# the rule-14 examples above are masculine, and the teacher copied «عطني» at women-only businesses (train_v1 batch 1)
WOMEN_ONLY_RULE = ("- Every customer of this business is a woman: always feminine forms, e.g. «عطيني اسمك الكريم», «تبين؟», "
                   "«أبشري», «تفضلي». Never «عطني», «تبي», «أبشر».\n")
DEPOSIT_RULE = ("- This business takes a deposit to confirm a booking ({policy}): after create_booking, say the booking is "
                "confirmed once the deposit is paid. Never call it confirmed before that.\n")
HOME_VISIT_RULE = ("- This business visits the customer at home: ask for their address (district and street) before booking, "
                   "pass it as `address` in create_booking, and never invite them to come in.\n")
CASUAL_OPENERS = ["يا هلا", "أهلين", "حياك", "مرحبا", "هلا والله", "هلا"]
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


def teacher_rules(register: str, business: dict, opener_word: str) -> str:
    formal = register == "formal"
    evening = "المساء" if formal else "المسا"
    rules = TEACHER_RULES + REGISTER_RULES[register].format(opener=opener_word) + TIME_WORD_RULE.format(
        morning="«الصباح»" if formal else "«الصبح»", evening=f"«{evening}»", evening_bare=evening,
        night="" if formal else f", and «الليل» from {NIGHT_START // 60}:00 («10 الليل»)")
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
                           "Say you had a bad reaction or pain after your last visit and are worried."])
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


def customer_turn(teacher: OpenRouterModel, sc: dict, transcript: list[str]) -> tuple[str | None, float]:
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
              f"Your goal: {sc['goal']} {'; '.join(style)}. Write ONLY your next WhatsApp message, usually 2-15 words, "
              "in natural Saudi dialect. Saudi words only: not Kuwaiti, Emirati, Bahraini, Egyptian, Levantine or Modern "
              "Standard Arabic (say صديقاتي not ربيعاتي, ابي not ابا, وش not شنو). Never Arabic in Latin letters. "
              "Say plainly what you want, like a real customer, and react to what the receptionist "
              "said. Only your FIRST message may greet: never start a later message with «وعليكم السلام» or return the "
              "receptionist's greeting, just answer. If your goal is done or cannot be done, reply exactly [END].")
    convo = "\n".join(transcript) or "(no messages yet: write your first message)"
    try:
        r = teacher.client.chat.completions.create(
            model=teacher.model, max_tokens=300,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": convo}],
            extra_body={"provider": {"order": teacher.providers, "only": teacher.providers, "data_collection": "deny"},
                        "reasoning": {"enabled": False}, "usage": {"include": True}})
    except Exception:  # never print error text: it can contain request details
        return None, 0.0
    usage = {"cost": (r.usage.model_extra or {}).get("cost")} if r.usage else {}
    text = (r.choices[0].message.content or "").strip().strip('"')
    return text, cost_usd(usage, teacher.price)


def generate_one(idx: int, sc: dict, teacher: OpenRouterModel, spec: tuple) -> tuple[dict | None, list[str], float]:
    _, styles, tools = spec
    b, meta = sc["business"], sc["meta"]
    now = datetime.fromisoformat(meta["now"])
    order = [tools[i] for i in meta["tools_order"]]
    rules = teacher_rules(meta["style"]["register"], b, sc["opener"])
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
DATE_THEN_DAY = re.compile(_date(2) + rf"\s*[(،,]?\s*(?:يوم\s+)?[وبل]?(?P<day>{_DAY})(?![{AR}])")
ISO_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
TIME_KIND = {**dict.fromkeys(["الصبح", "الصباح", "صباحا", "صباحاً"], "morning"),
             **dict.fromkeys(["الظهر", "ظهرا", "ظهراً"], "noon"), **dict.fromkeys(["العصر", "عصرا", "عصراً"], "asr"),
             **dict.fromkeys(["المسا", "المساء", "مساء", "مساءً"], "evening"),
             **dict.fromkeys(["الليل", "بالليل", "ليلا", "ليلاً"], "night")}
# longest first, so «المساء» is not read as «المسا»
TIME_WORDS = "(?:" + "|".join(sorted(TIME_KIND, key=len, reverse=True)) + ")"
# decisions_v4 rule 11, a clock rule: minutes of the day each word covers (ends above 1440 run past midnight)
NIGHT_START, NIGHT_TOLERANCE = 20 * 60, 60  # casual «الليل» "late"; 19:00-19:59 is flagged, not rejected
TIME_WINDOWS = {"morning": (3 * 60, 12 * 60), "evening": (12 * 60, 27 * 60), "night": (NIGHT_START, 27 * 60)}
CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_PART = r"(ونص|ونصف|وربع|الا ربع|إلا ربع)"
SPOKEN = re.compile(rf"(?:الساعة|الساعه)\s*(\d{{1,2}})(?!\d|:)(?:\s*{_PART})?"
                    rf"|(?<!\d|:)(\d{{1,2}})\s*{_PART}?\s*{TIME_WORDS}")
TIME_WITH_WORD = re.compile(rf"(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*{_PART}?\s*({TIME_WORDS})")
# formal time words are الصباح / الظهر / العصر / المساء (decisions_v3 rule 11)
FORMAL_CASUAL_TIME = re.compile(r"\d\s*(?:ونص\s*|وربع\s*)?(?:الصبح|المسا(?!ء)|الليل|بالليل)")
FORMAL_BANNED = ["يا قلبي", "حبيبتي"]
BANNED_PHRASES = ["ننطرك", "عال العال", "تأكد لي", "بيواصلونك", "يواصلونك"]  # rules 5, 16, 17
# rule 18: Modern Standard Arabic duals; Saudi says «حجزين», «موعدين»
MSA_DUALS = ["حجزان", "موعدان", "وقتان", "يومان", "ساعتان", "خياران", "شخصان", "خدمتان", "جلستان", "حصتان",
             "طاولتان", "قاعتان", "غرفتان", "فرعان"]
MSA_DUAL_RE = re.compile(rf"(?<![{AR}])[وبل]?({'|'.join(MSA_DUALS)})(?![{AR}])")
# masculine forms addressed to the customer, rejected at a women-only business (pilot_v3 gen-00000)
MASCULINE = ["عطني", "تبي", "تبغى", "تحب", "تقدر", "تامر", "تآمر", "أبشر", "ابشر", "تفضل", "خبرني", "اختار",
             "ارسل", "أرسل", "تكفى", "حاب", "متأكد"]
MASCULINE_RE = re.compile(rf"(?<![{AR}])[وف]?({'|'.join(MASCULINE)})(?![{AR}])")
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
HOURS_WORDS = re.compile(r"نفتح|نقفل|نسكر|يفتح|يقفل|يسكر|تفتح|تقفل|تسكر|مفتوح|دوام|يوقف|نبدأ|يبدأ|نخلص")
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


def time_word_problems(text: str, known24: dict, hours24: dict) -> tuple[list[str], list[str]]:
    """A time-of-day word must fit the hour it names (decisions_v4 rule 11: morning before 12:00,
    evening from 12:00, casual «الليل» late; «الظهر» and «العصر» are not time labels). The hour comes
    from the tools when the time is one of theirs (so «12 المساء» for a 12:00 slot is noon, not
    midnight); in a sentence that states opening hours («من 8 الصبح لين 8 المسا») the opening hours
    count too. Returns (problems, flags): «الليل» up to NIGHT_TOLERANCE before NIGHT_START is a flag."""
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
        if kind not in TIME_WINDOWS:
            bad.append(f"{said}: «الظهر / العصر» are not time labels (say الصباح / المساء)")
            continue
        cands = {h * 60 + m} if h > 12 else lookup.get(clock12(h, m)) or {h % 12 * 60 + m, (h % 12 + 12) * 60 + m}
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
    handoff_done, booked, first_reply, first_user, last_user = False, False, True, None, ""
    # slots the tools listed for today that have already passed (the backend lists the whole day)
    now = datetime.fromisoformat(meta["now"])
    now_min = now.hour * 60 + now.minute
    past_today, other_days = set(), set()
    for m in msgs:
        if m["role"] == "tool" and m.get("name") == "get_available_slots":
            try:
                res = json.loads(m["content"])
            except ValueError:
                continue
            for t in res.get("slots") or []:
                if res.get("date") == str(today) and to_min(t) < now_min:
                    past_today.add(clock12(*map(int, t.split(":"))))
                elif res.get("date") != str(today):
                    other_days.add(clock12(*map(int, t.split(":"))))
    for i, m in enumerate(msgs):
        if m["role"] == "user":
            text = m["content"]
            allowed_customer |= {clock12(h, mm) for h, mm in text_times(text)}
            allowed_customer |= {clock12(int(n), 0) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", text.translate(AR_DIGITS))
                                 if 1 <= int(n) <= 24}
            if FEMALE_NAME.search(text) or FEMALE_SELF.search(text):
                women = True
            if ENGLISH_PHRASE.search(text):
                problems.append(f"English phrase in a customer line: «{text[:40]}»")
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
        problems += day_slot_problems(text, today, dated, allowed_customer | (stated & hours))
        # a slot already past today, offered (pilot_v3 gen-00048: 13:00-17:00 offered at 18:31)
        passed = sorted(({clock12(*t) for t in text_times(text)} & past_today) - other_days - allowed_customer)
        if passed:
            problems.append("offers a time already past today: " + ", ".join(f"{h}:{mm:02d}" for h, mm in passed)
                            + f" (now {now:%H:%M})")
        # rule 11: the time-of-day word fits the hour
        bad_words, near_words = time_word_problems(text, known24, hours24)
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
        # rule 15: health or care tips (a word list cannot tell them from practical tips)
        if HEALTH_TIP.search(text):
            flags.append(f"possible health tip «{HEALTH_TIP.search(text).group(0)}»")
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
        first_reply = False
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


def run_report(kept: list[dict], rejected: list[dict]) -> str:
    """Per-run summary: formal pass rate, rejections per check, and the opener mix (1g)."""
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
    return "\n".join(lines)


def leak_score(line: str, test_grams: list) -> float:
    """Highest 3-gram overlap with any test/dev customer line. Lines under 5 words («السلام عليكم ورحمة الله»)
    are greetings and small talk that every conversation shares, not leaked test content, so they score 0."""
    if len(line.split()) < 5:
        return 0.0
    g = trigrams(line)
    return max((jaccard(g, t) for t in test_grams), default=0.0)


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
            problems += reply_problems(text, Context(short, rec["messages"][:i]))
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
    recs = [json.loads(l) for p in (keep_path, reject_path) if p.exists() for l in p.read_text(encoding="utf-8").splitlines()]
    kept, rejected = [], []
    for r in sorted(recs, key=lambda r: r["id"]):
        r.pop("problems", None)
        r.pop("flags", None)
        problems = check(r, (businesses, styles, tools), tok, test_grams) if "messages" in r else ["generation failed"]
        (rejected if problems else kept).append({**r, **({"problems": problems} if problems else {})})
    for path, rows in ((keep_path, kept), (reject_path, rejected)):
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(run_report(kept, rejected))


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
                        "; ".join(r.get("flags", [])), render(r), "", ""])
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
    a = ap.parse_args()
    {"generate": cmd_generate, "sheet": cmd_sheet, "recheck": cmd_recheck, "import-review": cmd_import_review}[a.cmd](a)
