"""Stage 6: unit tests for the review-rule checks in datagen.rule_checks (no API calls).

Every check gets at least one hand-made reply that must pass and one that must fail.

Run: uv run python scripts/test_datagen.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from build_testset import trigrams
from datagen import leak_score, opener, repair_lists, rule_checks, train_tools
from prompt import load_spec

ROOT = Path(__file__).resolve().parent.parent
BUSINESSES = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
CLINIC = next(b for b in BUSINESSES.values() if b["schedule"]["Mon"] == "16:00-23:00")  # opens 16:00
SALON = next(b for b in BUSINESSES.values() if b["customers"] == "women only")
NOW = "2026-11-05T17:00"  # a Thursday
PRAYER = {"Asr": "15:00", "Maghrib": "17:15", "Isha": "18:45"}
failures = 0


def tool(name: str, args: dict, result: dict, n: int = 1) -> list[dict]:
    return [{"role": "assistant", "tool_calls": [{"id": f"call_{n}", "type": "function",
                                                  "function": {"name": name, "arguments": args}}]},
            {"role": "tool", "tool_call_id": f"call_{n}", "name": name, "content": json.dumps(result, ensure_ascii=False)}]


def record(messages: list[dict], register: str = "casual", scenario: str = "booking", prayer: dict = PRAYER) -> dict:
    return {"scenario": scenario, "meta": {"now": NOW, "style": {"register": register, "warmth": "warm", "emoji": "on"},
                                           "prayer_times": prayer}, "messages": messages}


def expect(name: str, rec: dict, ok: bool, business: dict = CLINIC, reason: str | None = None) -> None:
    global failures
    problems, _ = rule_checks(rec, business)
    good = (not problems) == ok and (reason is None or any(reason in p for p in problems))
    failures += not good
    print(f"{'ok  ' if good else 'FAIL'} {name:62s} {'passes' if not problems else problems[0][:70]}")


USER = {"role": "user", "content": "ابي احجز تنظيف"}  # names no day: the test clinic is closed on the Friday «بكرة» would be
SLOTS = tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-06"},
             {"date": "2026-11-06", "slots": ["16:30", "18:00"]})


def reply(text: str) -> dict:
    return {"role": "assistant", "content": text}


# 1a: formal opener and words
expect("formal first reply with «هلا» fails", record([USER, reply("وعليكم السلام، هلا والله، وش تبي؟")], "formal"), False, reason="هلا")
expect("formal first reply with «حياك الله» passes", record([USER, reply("وعليكم السلام، حياك الله، وش الخدمة؟")], "formal"), True)
expect("casual first reply with «هلا» passes", record([USER, reply("هلا والله، وش تبي؟")], "casual"), True)
expect("formal reply with «حبيبتي» fails", record([USER, reply("حياك الله حبيبتي")], "formal"), False, reason="حبيبتي")
# rule 11: formal time words are الصباح / المساء
expect("formal «4 ونص العصر» fails (decisions_v4)", record([USER] + SLOTS + [reply("حياك الله، متاح 4 ونص العصر")], "formal"), False, reason="prayer time")
expect("formal «6 المسا» fails (casual word)", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المسا")], "formal"), False, reason="casual time words")
expect("formal «6 المساء» passes", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المساء")], "formal"), True)
# 1b: exact times
expect("slot 16:30 written «4 المسا» fails", record([USER] + SLOTS + [reply("عندنا 4 المسا")]), False, reason="time not from a tool")
expect("slot 16:30 written «4 ونص المسا» passes", record([USER] + SLOTS + [reply("عندنا 4 ونص المسا")]), True)
expect("slot written «16:30» fails (24-hour clock, batch 06)", record([USER] + SLOTS + [reply("عندنا 16:30 أو 18:00")]), False, reason="24-hour")
expect("slot 18:00 written «6 المسا» passes", record([USER] + SLOTS + [reply("عندنا 6 المسا")]), True)
expect("opening hour in an info reply passes", record([{"role": "user", "content": "متى تفتحون"}, reply("نفتح 4 المسا")]), True)
expect("opening hour while offering slots fails", record([USER] + SLOTS + [reply("عندنا 4 المسا أو 6 المسا")]), False)
expect("stated opening hour while offering slots passes (pilot_v2 gen-00006)",
       record([USER] + SLOTS + [reply("نفتح 4 المسا، والمتاح 4 ونص المسا")]), True)
expect("a slot time inside an hours clause must still be an hour", record([USER] + SLOTS + [reply("نفتح 5 المسا")]), False)
# 1c: days against the clock (now = Thursday 5 Nov)
expect("«اليوم الجمعة» on a Thursday fails", record([USER, reply("اليوم الجمعة مسكرين")]), False, reason="«اليوم»")
expect("«اليوم الخميس» passes", record([USER, reply("اليوم الخميس عندنا مواعيد")]), True)
expect("«بكرة السبت» on a Thursday fails", record([USER, reply("بكرة السبت فيه")]), False)
expect("«السبت بعد بكره» passes", record([USER, reply("السبت بعد بكره ما فيه")]), True)
expect("«الخميس 6 نوفمبر» fails (it is a Friday)", record([USER] + SLOTS + [reply("الخميس 6 نوفمبر فيه 4 ونص المسا")]), False, reason="6/11")
expect("«الجمعة 6 نوفمبر» passes", record([USER] + SLOTS + [reply("الجمعة 6 نوفمبر فيه 4 ونص المسا")]), True)
# 1d, 1e
expect("reply with «...» fails", record([USER, reply("الموافق...")]), False, reason="...")
expect("«ننطرك» fails", record([USER, reply("ننطرك بكرة")]), False, reason="ننطرك")
expect("«ننتظرك» passes", record([USER, reply("ننتظرك بكرة")]), True)
expect("«عال العال» fails", record([USER, reply("كله عال العال")]), False, reason="عال العال")
# 1f: feminine forms need evidence
expect("«أبشري» with no sign of a woman fails", record([USER, reply("أبشري")]), False, reason="feminine")
expect("«أبشري» after a female name passes", record([{"role": "user", "content": "باسم نورة"}, reply("أبشري")]), True)
expect("«أبشري» after «انا فاضية» passes", record([{"role": "user", "content": "انا فاضية الأحد"}, reply("أبشري")]), True)
expect("«أبشري» at a women-only business passes", record([USER, reply("أبشري")]), True, business=SALON)
expect("«تبين» after «انا وربيعاتي ٤ بنات» passes (pilot gen-00049)",
       record([{"role": "user", "content": "انا وربيعاتي ٤ بنات"}, reply("تبين أحجز لك؟")]), True)
expect("masculine «تبيني ألغيه» passes (pilot_v2 gen-00048)", record([USER, reply("تبيني ألغيه؟")]), True)
expect("masculine «ولا تنسى تعطيني الحي» passes (pilot_v2 gen-00025)", record([USER, reply("ولا تنسى تعطيني الحي والشارع")]), True)
expect("«وتبين» with no sign of a woman fails", record([USER, reply("وتبين أحجز لك؟")]), False, reason="feminine")
expect("«السبت بعد بكره كذلك» passes (pilot gen-00028)",record([USER, reply("السبت بعد بكره كذلك ما فيه")]), True)
# rule 7: after a handoff
HANDOFF = tool("handoff_to_human", {"reason": "x"}, {"status": "queued", "expected_wait_min": 10})
expect("after handoff «برد عليك ثواني» fails", record([USER] + HANDOFF + [reply("حولت طلبك، برد عليك ثواني")]), False, reason="handoff")
expect("after handoff «الفريق بيتواصل معك» passes", record([USER] + HANDOFF + [reply("حولت طلبك والفريق بيتواصل معك خلال 10 دقايق")]), True)
expect("after handoff «إن تأخر عليك… وأتابع لك» passes (accepted phrase)",
       record([USER] + HANDOFF + [reply("الانتظار تقريبًا 10 دقايق. إن تأخر عليك الوضع، قل لي وأتابع لك.")]), True)
# rule 10: claimed actions
expect("«سجلت ملاحظتك» with no tool fails", record([USER, reply("سجلت ملاحظتك")]), False, reason="سجلت")
expect("«حولت طلبك» with no handoff fails", record([USER, reply("حولت طلبك للإدارة")]), False, reason="transferred")
BOOK = tool("create_booking", {"service_id": "cleaning", "date": "2026-11-06", "time": "16:30", "customer_name": "x"},
            {"booking_id": "B-1", "status": "confirmed"}, 2)
expect("«سجلت حجزك» right after create_booking passes", record([USER] + SLOTS + BOOK + [reply("سجلت حجزك 4 ونص المسا")]), True)
# home visits: create_booking carries the address
HOME = next(b for b in BUSINESSES.values() if "home visit" in b["type"])
HOME_ARGS = {"service_id": "cleaning", "date": "2026-11-06", "time": "16:30", "customer_name": "x"}
expect("home-visit booking without an address fails",
       record([USER] + SLOTS + tool("create_booking", HOME_ARGS, {"booking_id": "B-1", "status": "confirmed"}, 2)
              + [reply("تم الحجز")]), False, business=HOME, reason="address")
expect("home-visit booking with an address passes",
       record([USER] + SLOTS + tool("create_booking", {**HOME_ARGS, "address": "حي النرجس، شارع الأمير"},
                                    {"booking_id": "B-1", "status": "confirmed"}, 2) + [reply("تم الحجز")]), True, business=HOME)
expect("in-shop booking without an address passes", record([USER] + SLOTS + BOOK + [reply("تم الحجز")]), True)
SPEC_TOOLS = load_spec()[2]
booking = next(t for t in train_tools(SPEC_TOOLS) if t["function"]["name"] == "create_booking")["function"]["parameters"]
for name, ok in [("training tools add an optional address", "address" in booking["properties"] and "address" not in booking["required"]),
                 ("spec/tools.json itself has no address", "address" not in json.dumps(SPEC_TOOLS))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# customer lines
expect("customer half-English «…and book» fails", record([{"role": "user", "content": "بستنى الموعد يناسبني and book"}, reply("تمام")]), False, reason="English")
expect("customer single English word passes", record([{"role": "user", "content": "ابي booking الأحد"}, reply("تمام")]), True)
expect("an English customer line fails (no English in the data)", record([{"role": "user", "content": "book a table please"}, reply("تمام")]), False, reason="English phrase")
# leakage: greetings are exempt, real copied lines are not
TEST_GRAMS = [trigrams("السلام عليكم ورحمة الله"), trigrams("ابي احجز قص شعر للولد بكرة بعد العصر")]
for name, ok in [("greeting identical to a test line is not leakage", leak_score("السلام عليكم ورحمة الله", TEST_GRAMS) == 0),
                 ("a copied test request is leakage", leak_score("ابي احجز قص شعر للولد بكرة بعد العصر", TEST_GRAMS) >= 0.6),
                 ("the full salaam is not leakage (batch 05 gen-00447)",
                  leak_score("السلام عليكم ورحمه الله وبركاته", [trigrams("السلام عليكم ورحمة الله وبركاته")]) == 0)]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v3 (pilot_v2 review) ----
def flags_of(rec: dict, business: dict = CLINIC) -> list[str]:
    return rule_checks(rec, business)[1]


def expect_flag(name: str, rec: dict, word: str, business: dict = CLINIC) -> None:
    global failures
    problems, flags = rule_checks(rec, business)
    good = not problems and any(word in f for f in flags)
    failures += not good
    print(f"{'ok  ' if good else 'FAIL'} {name:62s} {flags[0][:70] if flags else (problems or ['no flag'])[0][:70]}")


GYM = BUSINESSES["train_gym_1"]  # open 06:00-24:00
NOON = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"},
            {"date": "2026-11-06", "slots": ["12:00", "13:30", "16:45", "21:00"]})
# rule 11 (decisions_v4): a clock rule. Morning before 12:00, evening from 12:00, casual «الليل» from 20:00;
# «الظهر» and «العصر» are not time labels
expect("noon slot written «12 المساء» passes", record([USER] + NOON + [reply("فيه 12 المساء")], "formal"), True, GYM)
expect("noon slot written «12 الظهر» fails (not a label)", record([USER] + NOON + [reply("فيه 12 الظهر")], "formal"), False, GYM, reason="prayer time")
expect("13:30 written «1 ونص العصر» fails (not a label)", record([USER] + NOON + [reply("فيه 1 ونص العصر")]), False, GYM, reason="prayer time")
expect("13:30 written «1 ونص المسا» passes (casual)", record([USER] + NOON + [reply("فيه 1 ونص المسا")]), True, GYM)
expect("noon slot written «12 الصبح» fails", record([USER] + NOON + [reply("فيه 12 الصبح")]), False, GYM, reason="does not fit")
expect("21:00 written «9 الليل» passes (casual)", record([USER] + NOON + [reply("فيه 9 الليل")]), True, GYM)
expect("21:00 written «9 الصبح» fails", record([USER] + NOON + [reply("فيه 9 الصبح")]), False, GYM, reason="does not fit")
EVENING = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"},
               {"date": "2026-11-06", "slots": ["10:30", "16:30", "18:00", "19:00"]})
expect("10:30 written «10 ونص المسا» fails", record([USER] + EVENING + [reply("فيه 10 ونص المسا")]), False, GYM, reason="does not fit")
expect("16:30 «4 ونص المساء» passes whatever the prayer times", record([USER] + EVENING + [reply("فيه 4 ونص المساء")], "formal",
       prayer={"Asr": "15:40", "Maghrib": "18:30", "Isha": "20:00"}), True, GYM)
expect("19:00 «7 الليل» fails (decisions_v13: «الليل» only from 8 pm)", record([USER] + EVENING + [reply("فيه 7 الليل")]), False, GYM, reason="does not fit")
expect("18:00 «6 الليل» fails", record([USER] + EVENING + [reply("فيه 6 الليل")]), False, GYM, reason="does not fit")
expect("«بعد العصر» even for a period the customer asked about fails (decisions_v15, rule 11 strict)",
       record([{"role": "user", "content": "ابي موعد بعد العصر"}] + EVENING + [reply("بعد العصر فيه 4 ونص المسا")]), False, GYM,
       reason="prayer time")
# rules 12 and 13: the salaam
SALAM_USER = {"role": "user", "content": "السلام عليكم ابي احجز"}
expect("first reply without «وعليكم السلام» fails (pilot_v2 gen-00043)", record([SALAM_USER, reply("حياك الله، وش الخدمة؟")], "formal"), False, reason="does not return")
expect("first reply «وعليكم السلام، حياك الله» passes", record([SALAM_USER, reply("وعليكم السلام، حياك الله، وش الخدمة؟")], "formal"), True)
expect("customer «وعليكم السلام» in a later message fails (rule 12)",
       record([SALAM_USER, reply("وعليكم السلام، حياك الله"), {"role": "user", "content": "وعليكم السلام ابي تنظيف"}, reply("أبشر")]),
       False, reason="customer starts a later message")
expect("a later reply opening with «وعليكم السلام» fails (pilot_v2 gen-00027)",
       record([SALAM_USER, reply("وعليكم السلام، حياك الله"), {"role": "user", "content": "ابي اشتكي"}, reply("وعليكم السلام، الله يعوضك")]),
       False, reason="later reply opens")
# rule 14, and «الكشف» from the old teacher example (pilot_v2 gen-00022)
expect("«وابشر باسمك الكريم» fails", record([USER, reply("تمام، وابشر باسمك الكريم")]), False, reason="ابشر باسم")
expect("«عطني اسمك الكريم» passes", record([USER, reply("تمام، عطني اسمك الكريم")]), True)
expect("«الكشف» at a gym fails", record([USER, reply("الكشف 75 ريال")]), False, GYM, reason="الكشف")
expect("«الكشف» at a clinic with a كشف service passes", record([USER, reply("الكشف 75 ريال")]), True)
# rule 15: health tips are a flag (a word list cannot tell them from practical tips)
expect_flag("«اشرب مويه» is flagged", record([USER, reply("خلك مرتاح واشرب مويه")]), "health tip")
# dates: ISO, any format next to a day name, every form of «بعد بكرة»
expect("ISO date in a reply fails (pilot_v2 gen-00016)", record([USER, reply("موعدك 2026-11-06")]), False, reason="ISO")
expect("«الأربعا 2026-11-10» fails (it is a Tuesday)", record([USER, reply("موعدك الأربعا 2026-11-10")]), False, reason="10/11")
expect("«الجمعة 6-11» passes", record([USER, reply("موعدك الجمعة 6-11")]), True)
expect("«الخميس 6/11» fails", record([USER, reply("موعدك الخميس 6/11")]), False, reason="06/11")
expect("«6 نوفمبر (الخميس)» fails", record([USER, reply("موعدك 6 نوفمبر (الخميس)")]), False, reason="06/11")
expect("«بعد بكرة يوافق الخميس» fails (it is a Saturday; gen-00023)", record([USER, reply("بعد بكرة يوافق الخميس")]), False, reason="بعد بكرة")
expect("«بعد بكرا السبت» passes", record([USER, reply("بعد بكرا السبت فيه")]), True)
# exact times: «ونص / وربع / إلا ربع» are minutes; a time after a day must be that day's slot
expect("16:45 written «5 الا ربع المسا» passes", record([USER] + NOON + [reply("فيه 5 الا ربع المسا")]), True, GYM)
expect("16:45 written «4 وربع المسا» fails", record([USER] + NOON + [reply("فيه 4 وربع المسا")]), False, GYM, reason="time not from a tool")
TWO_DAYS = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"}, {"date": "2026-11-06", "slots": ["12:00"]}) + \
    tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-07"}, {"date": "2026-11-07", "slots": ["12:30"]}, 2)
expect("Friday's 12:00 written «بكرة الجمعة 12 ونص» fails (pilot_v2 gen-00019)",
       record([USER] + TWO_DAYS + [reply("بكرة الجمعة 12 ونص المسا، وبعده السبت 12 ونص المسا")]), False, GYM, reason="not a slot on Fri")
expect("each day with its own slot passes", record([USER] + TWO_DAYS + [reply("بكرة الجمعة 12 المسا، وبعده السبت 12 ونص المسا")]), True, GYM)
expect("a time just before its day name passes", record([USER] + TWO_DAYS + [reply("الجمعة 12 المسا، و12 ونص المسا السبت")]), True, GYM)
# placeholder names, «محجوز لك» before a booking
PLACEHOLDER = tool("create_booking", {"service_id": "cleaning", "date": "2026-11-06", "time": "16:30", "customer_name": "غير معروف"},
                   {"booking_id": "B-1", "status": "confirmed"}, 2)
expect("create_booking with «غير معروف» fails (pilot_v2 gen-00037)", record([USER] + SLOTS + PLACEHOLDER + [reply("تم")]), False, reason="placeholder")
expect("«محجوز لك» before create_booking fails (pilot_v2 gen-00000)", record([USER] + SLOTS + [reply("4 ونص المسا محجوز لك")]), False, reason="محجوز لك")
expect("«محجوز لك» after create_booking passes", record([USER] + SLOTS + BOOK + [reply("4 ونص المسا محجوز لك")]), True)
expect("«كله محجوز» (fully booked) passes", record([USER] + SLOTS + [reply("الصبح كله محجوز، فيه 4 ونص المسا")]), True)
# gender evidence: only what the customer says about herself, as whole words
expect("«موعد» is not the name «وعد»", record([{"role": "user", "content": "ابي موعد بكرة"}, reply("أبشري")]), False, reason="feminine")
expect("«تكفين» (said to the receptionist) is not evidence", record([{"role": "user", "content": "الغيه تكفين"}, reply("أبشري")]), False, reason="feminine")
expect("«حبيتي تحجزين» with no evidence fails (pilot_v2 gen-00012)", record([USER, reply("إذا حبيتي تحجزين قولي")]), False, reason="feminine")
expect("«زوجتي حامل» (a man speaking) is not evidence", record([{"role": "user", "content": "زوجتي حامل"}, reply("أبشري")]), False, reason="feminine")
expect("«انا حامل» is evidence", record([{"role": "user", "content": "انا حامل"}, reply("أبشري")]), True)
expect("«أنا متأكدة» is evidence", record([{"role": "user", "content": "أنا متأكدة"}, reply("أبشري")]), True)
expect("«انا بالخدمة»-style phrase is not evidence", record([{"role": "user", "content": "انا بالسيارة"}, reply("أبشري")]), False, reason="feminine")
expect("the name «وعد» is evidence (pilot_v2 gen-00044)", record([{"role": "user", "content": "وعد"}, reply("أبشري")]), True)
expect_flag("an unlisted feminine verb «ترسلين» is flagged", record([USER, reply("ممكن ترسلين الموقع؟")]), "possible feminine")
expect("«تمرين» (a noun) is not flagged or rejected", record([USER, reply("التمرين ساعة، وفيه تمرين بكرة")]), True, GYM)
# pilot_v3 false rejections
expect("«وبعد بكرة السبت» is read as «بعد بكرة» (pilot_v3 gen-00014)", record([USER, reply("وبعد بكرة السبت فيه")]), True)
expect("«وبعد بكرة الخميس» on a Thursday still fails", record([USER, reply("وبعد بكرة الخميس فيه")]), False, reason="بعد بكرة")
expect("the name in texting spelling «نوره» is evidence (pilot_v3 gen-00036)",
       record([{"role": "user", "content": "اسمي نوره محمد"}, reply("إذا احتجتي شي خبريني")]), True)
CAR = BUSINESSES["train_car_service_1"]  # 08:00-20:00
SAT = tool("get_available_slots", {"service_id": "x", "date": "2026-11-07"}, {"date": "2026-11-07", "slots": ["08:00", "08:30"]})
expect("closing hour «لين 8 المسا» in an hours sentence passes (pilot_v3 gen-00044)",
       record([USER] + SAT + [reply("دوامنا من 8 الصبح لين 8 المسا. عندك 8 الصبح و8 ونص الصبح")]), True, CAR)
expect("the same «8 المسا» offered as the 08:00 slot fails",
       record([USER] + SAT + [reply("عندك 8 المسا")]), False, CAR, reason="does not fit")
# ---- decisions_v4 (pilot_v3 review) ----
# slots already past today (NOW = Thursday 5 Nov, 17:00)
TODAY = tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-05"},
             {"date": "2026-11-05", "slots": ["13:00", "14:00", "18:00"]})
expect("offering today's 13:00 at 17:00 fails (pilot_v3 gen-00048)", record([USER] + TODAY + [reply("اليوم فيه 1 المسا أو 6 المسا")]),
       False, reason="already past today")
expect("offering only today's 18:00 at 17:00 passes", record([USER] + TODAY + [reply("اليوم فيه 6 المسا")]), True)
TWICE = tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-05"},
             {"date": "2026-11-05", "slots": ["07:00", "19:00"]})
expect("«7 المساء» for today's 19:00 passes when 07:00 has passed (batch 08 gen-00780)",
       record([USER] + TWICE + [reply("اليوم فيه 7 المساء")]), True)
expect("«7 الصبح» for today's past 07:00 still fails", record([USER] + TWICE + [reply("اليوم فيه 7 الصبح")]),
       False, reason="already past today")
expect("«والسبت» after a date starts a new item (batch 08 gen-00748)",
       record([USER, reply("فيه الجمعة 6 نوفمبر، والسبت 7 نوفمبر")]), True)
expect("a wrong day right after a date still fails", record([USER, reply("فيه 6 نوفمبر السبت")]), False, reason="called")
expect("booking today's 14:00 at 17:00 fails",
       record([USER] + TODAY + tool("create_booking", {"service_id": "cleaning", "date": "2026-11-05", "time": "14:00", "customer_name": "فهد"},
                                    {"booking_id": "B-1", "status": "confirmed"}, 2) + [reply("تم الحجز")]), False, reason="already past")
expect("a past hour that is also tomorrow's slot passes",
       record([USER] + TODAY + tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-06"},
                                    {"date": "2026-11-06", "slots": ["13:00"]}, 2) + [reply("بكرة الجمعة فيه 1 المسا")]), True)
# masculine forms at a women-only business (pilot_v3 gen-00000)
expect("«وعطني اسمك» at a women-only salon fails", record([USER, reply("تمام، وعطني اسمك الكريم")]), False, SALON, reason="masculine")
expect("«عطيني اسمك» at a women-only salon passes", record([USER, reply("تمام، عطيني اسمك الكريم")]), True, SALON)
expect("«تبي» at a women-only salon fails", record([USER, reply("تبي أحجز لك؟")]), False, SALON, reason="masculine")
expect("«عطني» at a mixed business passes", record([USER, reply("عطني اسمك الكريم")]), True)
# rule 18: Modern Standard Arabic duals (pilot_v3 gen-00035)
expect("«عندك حجزان» fails", record([USER, reply("عندك حجزان عندنا")]), False, reason="dual")
expect("«عندك حجزين» passes", record([USER, reply("عندك حجزين عندنا")]), True)
# rules 16, 17
expect("«تأكد لي تبغى نلغيه» fails", record([USER, reply("تأكد لي تبغى نلغيه؟")]), False, reason="تأكد لي")
expect("«أكد لي، تبغى تلغيه» passes", record([USER, reply("أكد لي، تبغى تلغيه؟")]), True)
expect("«الفريق بيواصلونك» fails", record([USER, reply("الفريق بيواصلونك خلال 10 دقايق")]), False, reason="بيواصلونك")
# the teacher's reasoning leaking into a reply (pilot_v3 gen-00010, gen-00029)
expect("English self-talk in a reply fails", record([USER, reply("Hmm, risk of contradicting the tool result here")]), False, reason="English sentence")
expect("Arabic self-talk «ما أبدأ بوعليكم السلام» fails", record([USER, reply("لا، ما أبدأ بوعليكم السلام مرة ثانية. وش الخدمة؟")]),
       False, reason="self-talk")
expect("brand names and a map link pass", record([USER, reply("الدفع مدى أو Apple Pay أو STC Pay، والموقع https://maps.example.com/train-spa-2")]), True)
expect("an English reply fails (no English in the data)", record([USER, reply("Cleaning is 200 riyals, it takes one hour.")]),
       False, reason="English sentence")
expect("self-talk fails", record([USER, reply("وش الخدمة؟ Let me check")]), False, reason="self-talk")
# teacher prompt: the clock rule and the hall deposit line
from datagen import EXAMPLES, teacher_rules  # noqa: E402
EXAMPLES.update({"formal": [], "casual": []})
HALL = BUSINESSES["train_hall_1"]
for name, ok in [("formal teacher rule says «المساء» from 12:00", "«المساء» from 12:00" in teacher_rules("formal", HALL, "x")),
                 ("teacher rules name prayer times only to forbid them",
                  all("Never name a prayer time" in line for line in teacher_rules("casual", GYM, "هلا").splitlines() if "Asr" in line)),
                 ("hall teacher prompt has the deposit line", "deposit" in teacher_rules("formal", HALL, "x")),
                 ("gym teacher prompt has no deposit line", "deposit to confirm" not in teacher_rules("formal", GYM, "x"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# train_v1 batch 1 false rejections (NOW = Thursday 5 Nov 17:00)
expect("«لبعد بكرة السبت» is read as «بعد بكرة» (batch 1 gen-00011, gen-00099)", record([USER, reply("ننقله لبعد بكرة السبت؟")]), True)
expect("«لبعد بكرة الخميس» still fails", record([USER, reply("ننقله لبعد بكرة الخميس؟")]), False, reason="بعد بكرة")
OPEN9 = tool("get_available_slots", {"service_id": "x", "date": "2026-11-07"}, {"date": "2026-11-07", "slots": ["09:00"]})
VET = BUSINESSES["train_vet_1"]  # 09:00-21:00
expect("«العيادة تفتح من 9 الصباح إلى 9 المساء» passes (batch 1 gen-00009)",
       record([USER] + OPEN9 + [reply("العيادة تفتح من 9 الصباح إلى 9 المساء. السبت فيه 9 الصباح")], "formal"), True, VET)
HANDOFF_EARLIER = tool("handoff_to_human", {"reason": "x"}, {"status": "queued", "expected_wait_min": 10})
expect("«رفعته للفريق» a turn after the handoff fails (decisions_v7; was allowed after batch 1)",
       record([USER] + HANDOFF_EARLIER + [reply("الفريق بيتواصلون معك"), {"role": "user", "content": "طيب"},
                                          reply("سؤالك رفعته للفريق وبيتواصلون معك خلال 10 دقايق")]),
       False, reason="sent nothing to the team")
expect("«رفعت» with no handoff still fails", record([USER, reply("سؤالك رفعته للفريق")]), False, reason="رفعت")
expect("«حابه أسأل» is evidence (batch 1 gen-00006)", record([{"role": "user", "content": "حابه أسأل عن المقهى"}, reply("تسلمين")]), True)
expect("«ماني متاكده» is evidence (batch 1 gen-00061)", record([{"role": "user", "content": "لا ماني متاكده"}, reply("تبغين نلغيه؟")]), True)
expect("«حابه» meaning 'I like it' (a man) is not evidence", record([{"role": "user", "content": "المكان حلو وانا حابه"}, reply("تسلمين")]),
       False, reason="feminine")
for name, ok in [("women-only teacher prompt has the feminine line", "«عطيني اسمك الكريم»" in teacher_rules("casual", SALON, "هلا")),
                 ("mixed business teacher prompt has no feminine line", "Every customer of this business is a woman" not in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v6 (batch 01 review): rules 22-24 and the builder checks ----
THANKS_USER = {"role": "user", "content": "شكرا يعطيك العافية"}
expect("«طال عمرك» fails (rule 22)", record([USER, reply("أبشر طال عمرك")]), False, reason="طال عمرك")
expect("«يا طويل العمر» fails", record([USER, reply("حياك الله يا طويل العمر")]), False, reason="طويل العمر")
# rule 23: emojis
expect("decorative 🌿 fails", record([USER, reply("حياك الله 🌿")]), False, reason="not allowed")
expect("🙏 fails", record([USER, reply("أبشر 🙏")]), False, reason="not allowed")
expect("✅ on «تم الحجز» passes", record([USER] + SLOTS + BOOK + [reply("تم الحجز ✅")]), True)
expect("✅ without «تم» fails", record([USER] + SLOTS + BOOK + [reply("حجزك جاهز ✅")]), False, reason="wrong place")
expect("✅ next to «تمام» (not «تم») fails", record([USER, reply("تمام ✅")]), False, reason="wrong place")
expect("🌹 answering thanks passes", record([USER, reply("تم"), THANKS_USER, reply("الله يعافيك 🌹")]), True)
expect("🌸 with no thanks fails", record([USER, reply("حياك الله 🌸")]), False, reason="wrong place")
expect("two emojis in one message fail", record([USER, reply("تم"), THANKS_USER, reply("الله يعافيك 🌹🌸")]), False, reason="2 emojis")
# rule 24: courtesy pairs
expect("«الله يعافيك، العفو» fails", record([USER, reply("تم"), THANKS_USER, reply("الله يعافيك، العفو")]), False, reason="العفو")
expect("«الله يعافيك، هذا واجبنا» passes", record([USER, reply("تم"), THANKS_USER, reply("الله يعافيك، هذا واجبنا")]), True)
expect("«ولو» answering thanks fails", record([USER, reply("تم"), THANKS_USER, reply("ولو، حياك الله")]), False, reason="ولو")
expect("«ولو تحتاج شي» (meaning 'if') passes", record([USER, reply("ولو تحتاج شي خبرني")]), True)
# formal words on customer lines, «الملغي» / «ألغى»
expect("customer «حسنا… في انتظار رد الفريق» fails (batch 01 gen-00045)",
       record([{"role": "user", "content": "حسنا في انتظار رد الفريق"}, reply("الفريق بيتواصلون معك")]), False, reason="customer line")
expect("customer «بانتظار ردكم» passes", record([{"role": "user", "content": "طيب بانتظار ردكم"}, reply("أبشر")]), True)
expect("«الملغي مجاني» fails", record([USER, reply("الملغي مجاني قبل 24 ساعة")]), False, reason="الملغي")
expect("«الحجز الملغي» passes", record([USER, reply("الحجز الملغي رقمه B-1")]), True)
expect("«ألغى لك الحجز» (first person) fails", record([USER, reply("أبشر، ألغى لك الحجز؟")]), False, reason="ألغى")
expect("«ألغي لك الحجز» passes", record([USER, reply("أبشر، ألغي لك الحجز؟")]), True)
# masculine forms after a woman's name (batch 01 gen-00092)
expect("«تبقى» after the customer says «نورة» fails", record([{"role": "user", "content": "اسمي نورة"}, reply("تبقى أحجز لك؟")]),
       False, reason="woman's name")
expect("«تبين» after «نورة» passes", record([{"role": "user", "content": "اسمي نورة"}, reply("تبين أحجز لك؟")]), True)
# the teacher hears about allowed emojis only when the switch is on (train_v1 batch 2)
for name, ok in [("emoji off: the teacher prompt names no emoji", not any(e in teacher_rules("casual", GYM, "هلا", "off") for e in "✅🌹🌸")),
                 ("emoji on: the teacher prompt names ✅ 🌹 🌸", all(e in teacher_rules("casual", GYM, "هلا", "on") for e in "✅🌹🌸"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v7 (batch 02 review) ----
H = tool("handoff_to_human", {"reason": "شكوى"}, {"status": "queued", "expected_wait_min": 10})
H2 = tool("handoff_to_human", {"reason": "تفاصيل إضافية"}, {"status": "queued", "expected_wait_min": 10}, 2)
NEW_DETAIL = {"role": "user", "content": "وكمان الموظف تأخر علي ساعة"}
expect("«وصلت ملاحظتك للفريق» after a new detail, no new handoff, fails (batch 02 gen-00104)",
       record([USER] + H + [reply("الفريق بيتواصلون معك خلال 10 دقايق"), NEW_DETAIL, reply("ملاحظتك وصلت للفريق")]),
       False, reason="sent nothing to the team")
expect("the same claim after a second handoff in that turn passes",
       record([USER] + H + [reply("الفريق بيتواصلون معك خلال 10 دقايق"), NEW_DETAIL] + H2 + [reply("ملاحظتك وصلت للفريق")]), True)
expect("«قلها لهم لما يتواصلون معك» passes",
       record([USER] + H + [reply("الفريق بيتواصلون معك خلال 10 دقايق"), NEW_DETAIL, reply("قلها لهم لما يتواصلون معك")]), True)
expect("«حولت طلبك للفريق» in the handoff turn passes", record([USER] + H + [reply("حولت طلبك للفريق وبيتواصلون معك")]), True)
HURRY_USER = {"role": "user", "content": "لا تتأخرون علي"}
expect("«الله يعينك» to «لا تتأخرون علي» fails (rule 25)",
       record([USER] + H + [reply("الفريق بيتواصلون معك"), HURRY_USER, reply("الله يعينك، ما نتأخر عليك")]), False, reason="الله يعينك")
expect("«أبشر، ما راح نتأخر عليك» passes",
       record([USER] + H + [reply("الفريق بيتواصلون معك"), HURRY_USER, reply("أبشر، ما راح نتأخر عليك بإذن الله")]), True)
# closings: assigned per conversation, independent of the scenario stream
from datagen import CLOSINGS, closing, closing_for, sample_scenario  # noqa: E402
import random  # noqa: E402
picks = [closing_for(i) for i in range(600)]
for name, ok in [("closing_for is stable", closing_for(7) == closing_for(7)),
                 ("all closings get used, none above 25%", set(picks) == set(CLOSINGS) and max(picks.count(c) for c in CLOSINGS) < 150),
                 ("teacher prompt carries the assigned closing", "«بأي وقت»" in teacher_rules("casual", GYM, "هلا", "off", "بأي وقت")),
                 ("«حنا تحت الخدمة» is no longer a rule example", "حنا تحت الخدمة" not in teacher_rules("formal", GYM, "x", "off")),
                 ("closing() reads the last reply", closing({"messages": [USER, reply("تم الحجز. حياك الله بأي وقت")]}) == "حياك الله بأي وقت")]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# complaints fit the business (batch 02 gen-00181: pain at a tutoring centre)
TUTOR = next(b for b in BUSINESSES.values() if "tutor" in b["type"] or "learning" in b["type"] or "language" in b["type"])
rng = random.Random(3)
goals = [sample_scenario(rng, [TUTOR]) for _ in range(300)]
complaint = [g["goal"] for g in goals if g["kind"] == "complaint" and "went wrong" in g["goal"]]
ok = bool(complaint) and all(TUTOR["type"] in g for g in complaint)
failures += not ok
print(f"{'ok  ' if ok else 'FAIL'} a health-style complaint names the business type ({TUTOR['type']})")
# batch 02 summary v2: courtesy answers need a courtesy to answer; the customer's «ابشر»
expect("«الله يحييك» answering a booking request fails (batch 02 gen-00198)", record([USER, reply("الله يحييك، وش الخدمة؟")]),
       False, reason="الله يحييك")
expect("«الله يعافيك» with no «يعطيك العافية» fails (batch 02 gen-00134)", record([USER, reply("تم"), {"role": "user", "content": "طيب"},
                                                                                 reply("الله يعافيك، تبي شي ثاني؟")]), False, reason="الله يعافيك")
expect("«الله يعافيك» answering «يعطيك العافية» passes", record([USER, reply("تم"), THANKS_USER, reply("الله يعافيك")]), True)
expect("«الله يحييك» answering «حياك الله» passes", record([{"role": "user", "content": "حياك الله، ابي احجز"}, reply("الله يحييك، وش الخدمة؟")]), True)
expect("the customer's own «الله يعافيك» is a courtesy to return (pilot_v3 gen-00005)",
       record([{"role": "user", "content": "ايه هذا، ألغيه الله يعافيك"}, reply("الله يعافيك، تم إلغاء الحجز")]), True)
expect("unprompted «الله يعافيك» mid-reply fails (rule 27, batch 06 gen-00378)", record([USER, reply("تم الحجز. الله يعافيك ويسعدك")]),
       False, reason="الله يعافيك")
ABSHIR_USER = {"role": "user", "content": "ابشر، اسمي فهد"}
expect("the customer's «ابشر» answered «أبشر» fails (batch 02 gen-00188)", record([USER, reply("عطني اسمك"), ABSHIR_USER, reply("أبشر، تم")]),
       False, reason="الله يبشرك")
expect("the customer's «ابشر» answered «الله يبشرك بالخير» passes", record([USER, reply("عطني اسمك"), ABSHIR_USER, reply("الله يبشرك بالخير، تم")]), True)
# ---- decisions_v9 (batch 03 review) ----
THANKS_ONLY = {"role": "user", "content": "تم، شكراً لكم"}
expect("«الله يحييك» answering «شكراً» fails (rule 29, batch 03 gen-00269)", record([USER, reply("تم"), THANKS_ONLY, reply("الله يحييك")]),
       False, reason="rule 29")
expect("«الله يحييك» closing a booking reply fails (batch 03 gen-00284)", record([USER, reply("تم الحجز. ننتظرك، والله يحييك")]),
       False, reason="rule 29")
expect("«العفو، هذا واجبنا» answering «شكراً» passes", record([USER, reply("تم"), THANKS_ONLY, reply("العفو، هذا واجبنا")]), True)
expect("«والمدير بيتواصل معك» fails (batch 03 gen-00260)", record([USER] + H + [reply("رفعت طلبك للفريق والمدير بيتواصل معك")]),
       False, reason="manager")
expect("«ووصلتها للمدير» fails (batch 03 gen-00250)", record([USER] + H + [reply("شكواك ووصلتها للمدير")]), False, reason="manager")
expect("«المدير» in a question passes", record([USER, reply("تبي تكلم المدير؟ أقدر أحول طلبك للفريق")]), True)
expect("«أنا نايف موظف الاستقبال، وأنا رجل» fails (rule 30, batch 03 gen-00212)",
       record([USER, reply("أنا نايف موظف الاستقبال، وأنا رجل")]), False, reason="rule 30")
expect("«أنا مساعد … وهنا عشان أخدمك» passes", record([USER, reply("أنا مساعد عيادة الابتسامة وهنا عشان أخدمك")]), True)
for name, ok in [("teacher prompt has the identity line with the business name",
                  f"«أنا مساعد {GYM['name']} وهنا عشان أخدمك»" in teacher_rules("casual", GYM, "هلا")),
                 ("teacher prompt has rule 34 (one option per line)", "each on its own line" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# batch 04 false rejections
expect("«ما عندي رقم المدير… لكن رفعت طلبك للفريق» passes (batch 04 gen-00304)",
       record([USER] + H + [reply("ما عندي رقم المدير أعطيك إياه، لكن رفعت طلبك للفريق وبيتواصلون معك خلال 10 دقايق")]), True)
expect("«ما أقدر أوصلك بالمدير مباشرة، لكن… الفريق بيتواصل» passes (gen-00352)",
       record([USER] + H + [reply("ما أقدر أوصلك بالمدير مباشرة، لكن الفريق بيتواصل معك خلال 10 دقايق")]), True)
expect("«سجلت طلبك إنك تبغى تكلم المدير بنفسك… والفريق بيتواصل» passes (gen-00392)",
       record([USER] + H + [reply("سجلت طلبك إنك تبغى تكلم المدير بنفسك، والفريق بيتواصل معك خلال 10 دقايق")]), True)
expect("«ما عندنا 8 المساء» echoing the customer's 8 pm passes (gen-00326)",
       record([{"role": "user", "content": "احجز لي ٨ المساء"}] + tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"},
              {"date": "2026-11-06", "slots": ["08:00", "13:00"]}) + [reply("ما عندنا 8 المساء، المتاح 8 الصباح أو 1 المساء")]), True, GYM)
expect("offering the 08:00 slot as «8 المساء» still fails",
       record([USER] + tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"},
              {"date": "2026-11-06", "slots": ["08:00", "13:00"]}) + [reply("المتاح 8 المساء أو 1 المساء")]), False, GYM, reason="does not fit")
# ---- decisions_v10 (batch 04 review) ----
expect("«الله يحييك» answering «حبيت أسلم عليكم» passes (rule 36, batch 01 gen-00075)",
       record([{"role": "user", "content": "الله يعافيك، بس حبيت أسلم عليكم."}, reply("الله يحييك، بأي وقت تفضل.")]), True)
expect("a customer line with «Receptionist:» fails (batch 04 gen-00394)",
       record([USER, reply("تمام"), {"role": "user", "content": "Receptionist: تم الحجز Customer: شكرا"}, reply("الله يعافيك")]),
       False, reason="role label")
expect("a customer «احجز لي ٠ المساء» fails (batch 04 gen-00318)",
       record([USER, reply("تمام"), {"role": "user", "content": "احجز لي ٠ المساء"}, reply("أبشر")]), False, reason="impossible time")
expect("«٥ جلسات» in a reply fails (batch 04 gen-00367)", record([USER, reply("الباقة ٥ جلسات، والفريق خلال 10 دقايق")]), False, reason="٠-٩")
expect("«5 جلسات» passes", record([USER, reply("الباقة 5 جلسات")]), True)
expect("«من 6 الصباح إلى 12 المساء» at a midnight closer fails (rule 35, batch 04 gen-00344)",
       record([{"role": "user", "content": "متى تفتحون"}, reply("نفتح من 6 الصباح إلى 12 المساء")], "formal"), False, GYM, reason="rule 35")
expect("«من 6 الصباح إلى 12 الليل» in a formal row passes", record([{"role": "user", "content": "متى تفتحون"},
       reply("نفتح من 6 الصباح إلى 12 الليل")], "formal"), True, GYM)
expect("formal «11 الليل» is still casual", record([{"role": "user", "content": "متى تسكرون"}, reply("نسكر 11 الليل")], "formal"),
       False, GYM, reason="casual time words")
expect("a noon slot «12 المساء» at a midnight closer passes", record([USER] + NOON + [reply("فيه 12 المساء")], "formal"), True, GYM)
for name, ok in [("teacher rule: midnight is «12 الليل»", "Midnight is «12 الليل»" in teacher_rules("formal", GYM, "x")),
                 ("teacher rule: search a group service for a group size", "group service" in teacher_rules("casual", GYM, "هلا")),
                 ("«حنا تحت الخدمة» closing comes with a lead-in (rule 37)",
                  "«بأي وقت تحتاجنا حنا تحت الخدمة»" in teacher_rules("casual", GYM, "هلا", "off", "حنا تحت الخدمة"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
expect("«ما نقدر نحجز قبل 7 الصباح، هذا وقت فتحنا» states hours (batch 05 gen-00489)",
       record([USER] + tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"}, {"date": "2026-11-06", "slots": ["07:30"]})
              + [reply("ما نقدر نحجز قبل 7 الصباح، هذا وقت فتحنا. المتاح 7 ونص الصباح")]), True, BUSINESSES["train_cafe_1"])
# ---- decisions_v11 (batch 05 review) ----
expect("a customer word mixing scripts «تسلمonmفضلين» fails (batch 05 gen-00476)",
       record([USER, reply("تم"), {"role": "user", "content": "تسلمonmفضلين"}, reply("الله يعافيك")]), False, reason="Latin letters inside")
expect("«ابي booking الأحد» (separate words) still passes", record([{"role": "user", "content": "ابي booking الأحد"}, reply("تمام")]), True)
for name, ok in [("teacher rule 39: give the real date before moving with a relative day", "حجزك أصلاً الثلاثاء 26" in teacher_rules("casual", GYM, "هلا")),
                 ("teacher rule: Thursday before a closed Friday is still offered", "Thursday" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v12 (batch 06 review) ----
expect("«تم إلغاء… الله يعافيك» after «اي لغوه» fails (batch 06 gen-00438)",
       record([USER, reply("تبي ألغيه؟"), {"role": "user", "content": "اي لغوه"}, reply("تم إلغاء حجزك. الله يعافيك، وإذا حبيت تحجز كلمني")]),
       False, reason="الله يعافيك")
expect("«10:30» (12-hour) still passes", record([USER] + tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"},
       {"date": "2026-11-06", "slots": ["10:30"]}) + [reply("عندنا 10:30 الصبح")]), True, GYM)
expect("a stray «٥» at the end of a customer line fails (batch 06 gen-00574)",
       record([USER, reply("تمام"), {"role": "user", "content": "بس ابي أضمن ما يتكرر نفس التعامل ٥"}, reply("أبشر")]), False, reason="stray digit")
for text in ("ابغى الساعه ٩", "يعني ٤ او ٥", "أشوفكم الأحد ٨", "ما يناسبني ابي بالليل يعني بعد 7"):
    expect(f"customer «{text}» keeps its digit", record([USER, reply("تمام"), {"role": "user", "content": text}, reply("أبشر")]), True, GYM)
for name, ok in [("teacher rule 40: nearest open day first", "nearest open day" in teacher_rules("casual", GYM, "هلا")),
                 ("teacher rule 41: «تبيني ألغيه لك؟»", "تبيني ألغيه لك؟" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v13 (batch 07 review) and the Stage 7 complaint finding ----
expect("the receptionist's «الله يعطيك العافية» fails (rule 42)", record([USER, reply("تم الحجز، الله يعطيك العافية")]), False, reason="rule 42")
expect("«حبيبتي» in a casual reply fails (rule 44)", record([USER, reply("أبشري حبيبتي")]), False, SALON, reason="rule 44")
expect("«فتكفى لا تتأخر» fails (rule 44)", record([USER, reply("نحفظ لك الطاولة، فتكفى لا تتأخر")]), False, reason="rule 44")
expect("the typo «إجانتنا» fails", record([USER, reply("الجمعة إجانتنا")]), False, reason="typo")
expect_flag("«دكتور» is flagged for the reviewer, not rejected", record([USER, reply("تبي دكتورة؟ أقدر أسأل الفريق")]), "medical word")
expect("«بحولك للفريق» without a handoff call fails (Stage 7 test, complaint-06)",
       record([USER, reply("سلامتك، بحولك للفريق وبيتواصلون معك")]), False, reason="without calling handoff")
expect("«بحولك للفريق» in the turn that calls handoff passes", record([USER] + H + [reply("سلامتك، بحولك للفريق وبيتواصلون معك")]), True)
expect("«أقدر أحول طلبك للفريق» (an offer) passes", record([USER, reply("أقدر أحول طلبك للفريق إذا تبي")]), True)
expect("«تبيني أحوله للفريق؟» (a question) passes", record([USER, reply("تبيني أحوله للفريق؟")]), True)
for before, after in [("والسبت عندنا 8 ونص الصبح و10 الصبح و12 ونص المسا و1 المسا.",
                       "والسبت عندنا\n8 ونص الصبح\n10 الصبح\n12 ونص المسا\n1 المسا."),                                   # gen-00619
                      ("ما عندنا تفصيل ثوب، عندنا قص شعر، سشوار، صبغة، ومكياج سهرة. تبين وحدة منها؟",
                       "ما عندنا تفصيل ثوب،\nعندنا\nقص شعر\nسشوار\nصبغة\nمكياج سهرة.\nتبين وحدة منها؟"),                  # gen-00648
                      ("عندنا خدمتين: تصوير شخصي (500 ريال، 60 دقيقة)، وتصوير عائلي (770 ريال، 90 دقيقة).",
                       "عندنا خدمتين: تصوير شخصي (500 ريال، 60 دقيقة)، وتصوير عائلي (770 ريال، 90 دقيقة).")]:   # gen-00699
    got = repair_lists(before)
    failures += got != after
    print(f"{'ok  ' if got == after else 'FAIL'} list repair «{before[:45]}»" + ("" if got == after else f" -> {got!r}"))
for name, ok in [("teacher rule 43: «سلامتك» and hand off at once", "«سلامتك»" in teacher_rules("casual", GYM, "هلا")),
                 ("teacher rule 39 (A): name a new date only after get_available_slots", "Name a new date only after get_available_slots" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v14 (batch 08 review) ----
expect("«يا الغالية» fails (rule 44 widened, gen-00728)", record([USER, reply("تم إلغاء موعدك يا الغالية")]), False, SALON, reason="rule 44")
expect("«يا طيب» fails (gen-00778)", record([USER, reply("بأي وقت يا طيب")]), False, reason="rule 44")
expect("the name instead passes", record([{"role": "user", "content": "اسمي سعد"}, reply("تم يا سعد")]), True)
expect("«الخميس عندنا متاح» before any lookup fails (rule 45, gen-00775)",
       record([USER, reply("الخميس عندنا متاح إن شاء الله، كم عددكم؟")]), False, reason="rule 45")
expect("«6 الصبح متاح» before any lookup fails (gen-00754)", record([USER, reply("طيب، 6 الصبح متاح. أي يوم تبغاه؟")]), False, reason="rule 45")
expect("«4 ونص المسا متاح» after the lookup passes", record([USER] + SLOTS + [reply("تمام، 4 ونص المسا متاح، عطني اسمك الكريم")]), True)
expect("«أشوف لك المتاح» (an offer to look) passes", record([USER, reply("عطني اليوم اللي تبغاه وأشوف لك المتاح من 4 المسا")]), True)
expect("«والاثنين متاحين» (both payment methods) passes (batch 09 gen-00890)",
       record([USER, reply("نقبل الكاش ومدى، والاثنين متاحين عندنا.")]), True)
expect("«يوم الاثنين متاح» before any lookup fails", record([USER, reply("يوم الاثنين متاح عندنا")]), False, reason="rule 45")
TWO = tool("get_my_bookings", {}, {"bookings": [
    {"booking_id": "B-1", "service": "حصة إنجليزي", "service_id": "en", "date": "2026-11-08", "time": "17:00"},
    {"booking_id": "B-2", "service": "اختبار تحديد مستوى", "service_id": "lv", "date": "2026-11-10", "time": "16:00"}]})


def cancel(bid: str, n: int = 2) -> list[dict]:
    return tool("cancel_booking", {"booking_id": bid}, {"booking_id": bid, "status": "cancelled"}, n)


ASK = reply("عندك حجزين: حصة إنجليزي الأحد 8 نوفمبر، 5 المسا، واختبار تحديد مستوى الثلاثاء 10 نوفمبر، 4 المسا. أيهم تبغى تلغيه؟")
expect("cancelling the booking the customer named passes",
       record([USER] + TWO + [ASK, {"role": "user", "content": "ألغي حصة الإنجليزي"}] + cancel("B-1") + [reply("تم الإلغاء")]), True)
expect("cancelling by its hour passes («حق ٤ المسا»)",
       record([USER] + TWO + [ASK, {"role": "user", "content": "الغي حق ٤ المسا"}] + cancel("B-2") + [reply("تم الإلغاء")]), True)
expect("a repeated «إيه، الغيه» that cancels the other booking fails (rule 46, gen-00751)",
       record([USER] + TWO + [ASK, {"role": "user", "content": "ألغي حصة الإنجليزي"}] + cancel("B-1") +
              [reply("تم إلغاء حصة الإنجليزي. باقي عندك اختبار تحديد مستوى الثلاثاء 10 نوفمبر."),
               {"role": "user", "content": "إيه، الغيه"}] + cancel("B-2", 3) + [reply("تم الإلغاء")]), False, reason="rule 46")
expect("«إيه، الغيه» answering «تقصد ألغي لك الاختبار بعد؟» passes",
       record([USER] + TWO + [reply("تقصد ألغي لك اختبار تحديد مستوى بعد؟"), {"role": "user", "content": "إيه، الغيه"}]
              + cancel("B-2") + [reply("تم الإلغاء")]), True)
expect("echoing the customer's «5 العصر» still fails (gen-00791)",
       record([{"role": "user", "content": "ابي 5 العصر"}] + SLOTS + [reply("ما فيه 5 العصر، فيه 4 ونص المسا")]), False, reason="prayer time")
# ---- decisions_v15 (batch 09 review) ----
expect("«7 المغرب» fails (rule 11 strict, gen-00866)", record([USER] + SLOTS + [reply("ما فيه 7 المغرب، فيه 4 ونص المسا")]), False, reason="prayer time")
expect("«المتاح بعد العصر:» fails", record([USER] + SLOTS + [reply("المتاح بعد العصر: 4 ونص المسا")]), False, reason="prayer time")
expect("«قبل المغرب» fails", record([USER] + SLOTS + [reply("فيه 4 ونص المسا قبل المغرب")]), False, reason="prayer time")
expect("«ما نفتح الفجر» fails", record([USER] + SLOTS + [reply("ما نفتح الفجر، فيه 4 ونص المسا")]), False, reason="prayer time")
expect("«8 العشاء» (a time) fails", record([USER] + SLOTS + [reply("فيه 8 العشاء")]), False, reason="prayer time")
expect("«العشاء» as dinner passes", record([USER] + SLOTS + [reply("العشاء عندنا من المنيو كامل، وفيه 4 ونص المسا")]), True)
expect("the service «الحمام المغربي» passes", record([USER] + SLOTS + [reply("الحمام المغربي متاح 4 ونص المسا")]), True)
CAFE2 = BUSINESSES["train_cafe_2"]  # open every day, so «بكرة» (a Friday here) is an open day
AFTER = tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-06", "after": "15:42"},
             {"date": "2026-11-06", "slots": ["16:30", "18:00"]})
expect("«بكرة بعد 3 ونص المسا» from after 15:42 passes (the prayer-word repair)",
       record([{"role": "user", "content": "ابي بكرة بعد العصر"}] + AFTER + [reply("المتاح بكرة الجمعة بعد 3 ونص المسا: 4 ونص المسا أو 6 المسا")]), True, CAFE2)
expect("«بعد 4 المسا» (not the after time) still fails",
       record([{"role": "user", "content": "ابي بكرة بعد العصر"}] + AFTER + [reply("المتاح بكرة الجمعة بعد 4 المسا: 4 ونص المسا")]), False, CAFE2, reason="not from a tool")
# ---- decisions_v16 (batch 10 review) ----
expect("formal «إلى 1 الليل» (after midnight) passes (gen-00933)",
       record([USER] + SLOTS + [reply("حياك الله، دوامنا إلى 1 الليل، وفيه 4 ونص المساء")], "formal"), True, BUSINESSES["train_cafe_2"])
expect("formal «11 الليل» still fails (say «11 المساء»)",
       record([USER] + SLOTS + [reply("حياك الله، دوامنا إلى 11 الليل")], "formal"), False, reason="casual time words")
PM5 = tool("get_available_slots", {"service_id": "cleaning", "date": "2026-11-06"}, {"date": "2026-11-06", "slots": ["17:00"]})
expect("the customer's «٥ الفجر» answered «ما ينفع 5 الصباح» passes (gen-00796 repair)",
       record([{"role": "user", "content": "ابي بكرة ٥ الفجر"}] + PM5 + [reply("ما ينفع 5 الصباح، فيه بكرة 5 المسا")]), True, CAFE2)
expect("the customer's «ست الصباح» in words answered «ما عندنا 6 الصباح» passes (batch 11 gen-01010)",
       record([{"role": "user", "content": "ابي بدري مثلا ست الصباح"}] + SLOTS + [reply("ما عندنا 6 الصباح، فيه 4 ونص المسا")]), True)
from datagen import closed_day_dates_ok, repair_courtesy  # noqa: E402
CAR2 = BUSINESSES["train_car_service_2"]  # closed on Fridays; NOW is Thursday 5 Nov, so 6 Nov is a Friday
NOW_DT = datetime.fromisoformat(NOW)
WRONG = ["dates [(6, 11)] match no real date in the conversation"]
for name, ok in [
        ("a closed day's date said to be closed is fine (decisions_v16)",
         closed_day_dates_ok(WRONG, "بكرة الجمعة 6 نوفمبر، وإحنا الجمعة مغلقين.", CAR2, NOW_DT) == []),
        ("a closed day's date offered as open still fails", closed_day_dates_ok(WRONG, "بكرة الجمعة 6 نوفمبر فيه 4 المسا.", CAR2, NOW_DT) == WRONG),
        ("an open day's date with «مغلقين» still fails",
         closed_day_dates_ok(WRONG, "بكرة 6 نوفمبر، وإحنا مغلقين.", BUSINESSES["train_cafe_2"], NOW_DT) == WRONG),
        ("courtesy repair: «العفو، الله يعافيك.» → «الله يعافيك.»", repair_courtesy("العفو، الله يعافيك.") == "الله يعافيك."),
        ("courtesy repair: «الله يعافيك، العفو 🌸» → «الله يعافيك 🌸»", repair_courtesy("الله يعافيك، العفو 🌸") == "الله يعافيك 🌸"),
        ("courtesy repair leaves «العفو يا مشاري، الله يعافيك» alone",
         repair_courtesy("العفو يا مشاري، الله يعافيك 🌹") == "العفو يا مشاري، الله يعافيك 🌹"),
        ("courtesy repair leaves «العفو» without «الله يعافيك» alone", repair_courtesy("العفو، هذا واجبنا") == "العفو، هذا واجبنا"),
        ("teacher: «الله يعافيك» alone, no «العفو», even with thanks", "even when the customer also thanked you" in teacher_rules("casual", GYM, "هلا")),
        ("teacher: «الاثنين» is not «both»", "«الاثنين» to mean \"both\"" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# ---- decisions_v17 (batch 11 review) ----
SEVEN_AM = tool("get_available_slots", {"service_id": "outdoor", "date": "2026-11-06"},
                {"date": "2026-11-06", "slots": ["07:00", "07:30", "08:30", "10:00", "11:30", "14:00"]})
expect("«ما فيه موعد 7 الليل بكرة» echoing the customer's «٧ بالليل» fails (rescued gen-00190)",
       record([{"role": "user", "content": "ابي احجز جلسة خارجية بكرة الساعة ٧ بالليل"}] + SEVEN_AM
              + [reply("للأسف ما فيه موعد 7 الليل بكرة، المتاح بكرة: 7 الصبح، و8 ونص الصبح")]), False, reason="does not fit")
for hour, slot in [(4, "16:00"), (5, "05:00"), (6, "18:00"), (7, "19:00")]:
    expect(f"«{hour} الليل» fails whatever the slot list holds ({slot})",
           record([USER, *tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"}, {"date": "2026-11-06", "slots": [slot]}),
                   reply(f"فيه بكرة {hour} الليل")]), False, reason="does not fit")
expect("the customer's «8 المساء» echoed while a tool lists 08:00 still passes",
       record([{"role": "user", "content": "ابي 8 المساء"}, *tool("get_available_slots", {"service_id": "x", "date": "2026-11-06"},
                                                                 {"date": "2026-11-06", "slots": ["08:00", "16:30"]}),
               reply("ما فيه 8 المساء، فيه 4 ونص المسا")]), True)
FRIDAY_ASK = {"role": "user", "content": "ابي احجز تغيير زيت بكرة"}  # NOW is Thursday; CAR2 is closed on Fridays
expect("a closed day answered with other days, not saying it is closed, fails (rule 47, gen-01059)",
       record([FRIDAY_ASK, reply("أقرب يوم متاح عندنا السبت، تبغى أشوف لك المواعيد؟")]), False, CAR2, reason="rule 47")
expect("«بكرة الجمعة إجازة عندنا» then another day passes",
       record([FRIDAY_ASK, reply("بكرة الجمعة إجازة عندنا، تبغى أشوف لك السبت؟")]), True, CAR2)
expect("«عندي موعد بكرة» (an existing booking) is not a request for the closed day (gen-01015)",
       record([{"role": "user", "content": "عندي موعد بكرة وابي اتاكد"}, reply("ما لقيت لك موعد مسجل، عطني اسمك الكريم")]), True, CAR2)
expect("«كيف الجو عندكم بكرة؟» on a closed day is small talk, not a request (batch 12 gen-01175)",
       record([{"role": "user", "content": "كيف الجو عندكم بكرة؟"}, reply("الجو ما عندي علم فيه، حنا بالخدمة")]), True, CAR2)
# run 4: the first move (run 3 learned «search_services first» from the data)
SEARCH = tool("search_services", {"query": "زيت"}, {"services": [{"id": "oil", "name": "تغيير زيت", "price_sar": 90, "duration_min": 30}]})
SAT = tool("get_available_slots", {"service_id": "oil", "date": "2026-11-07"}, {"date": "2026-11-07", "slots": ["10:00"]})
expect("a closed-day request answered with a service search first fails (run 3)",
       record([FRIDAY_ASK] + SEARCH + [reply("بكرة الجمعة إجازة عندنا، تبغى أشوف لك السبت؟")]), False, CAR2, reason="closed-day request")
expect("a closed-day request answered by «إجازة» first passes",
       record([FRIDAY_ASK, reply("بكرة الجمعة إجازة عندنا، تبغى أشوف لك السبت؟")]), True, CAR2)
expect("a closed-day request answered with the open Saturday's slots first passes",
       record([FRIDAY_ASK] + SAT + [reply("بكرة الجمعة إجازة عندنا، والسبت فيه 10 الصبح")]), True, CAR2)
EARLY_ASK = {"role": "user", "content": "ابي احجز تغيير زيت بدري قبل تفتحون"}
for name, ok in [("teacher: offer the open day by name only, the date after the slot lookup (focus_v2 first try)",
                  "by its name only" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
expect("a closed-scenario first message with no time, answered with a service search, passes (focus_v2 gen-00002)",
       record([{"role": "user", "content": "ابي احجز تغيير زيت"}] + SEARCH + [reply("تغيير الزيت 90 ريال، أي يوم يناسبك؟")], scenario="closed"),
       True, CAR2)
expect("a request before opening answered with the hours first passes",
       record([EARLY_ASK, reply("نفتح 8 الصبح، تبغى أشوف لك أول موعد؟")], scenario="closed"), True, CAR2)
UNKNOWN_Q = {"role": "user", "content": "عندكم خصم للطلاب؟"}
HANDOFF_Q = tool("handoff_to_human", {"reason": "يسأل عن خصم الطلاب"}, {"status": "queued", "expected_wait_min": 10})
expect("an unknown question answered with a service search first fails (run 3)",
       record([UNKNOWN_Q] + SEARCH + [reply("ما عندي علم، الفريق بيتواصل معك")], scenario="unknown"), False, CAR2, reason="nobody here can answer")
expect("an unknown question answered with a handoff first passes",
       record([UNKNOWN_Q] + HANDOFF_Q + [reply("ما عندي علم فيها، والفريق بيتواصلون معك خلال 10 دقايق")], scenario="unknown"), True, CAR2)
ONE_BOOKING = tool("get_my_bookings", {}, {"bookings": [{"booking_id": "B-1", "service": "حصة", "service_id": "x",
                                                         "date": "2026-11-11", "time": "12:00"}]})
for text, ok in [("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى نأخره للاثنين 9 نوفمبر؟", False),   # gen-00830
                 ("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى نقدمه للاثنين 9 نوفمبر؟", True),
                 ("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى نأخره للجمعة 13 نوفمبر؟", True),
                 ("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى نقدمه للجمعة 13 نوفمبر؟", False),
                 ("حجزك الأربعاء 11 نوفمبر، ولا تتأخر علينا", True),
                 ("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى تأخره للاثنين 9؟", False),     # batch 12 gen-01180: «لل»
                 ("حجزك أصلاً الأربعاء 11 نوفمبر، تبغى أقدمه للاثنين 9؟", True)]:
    expect(f"move wording: «{text[-28:]}»", record([USER] + ONE_BOOKING + [reply(text)]), ok, reason=None if ok else "say «")
# ---- decisions_v18 (focus set review): tests on the reviewed rows themselves ----
FOCUS = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "train" / "focus_v1.jsonl").read_text(encoding="utf-8").splitlines()}


def focus_checks(i: str) -> tuple[list[str], list[str]]:
    r = FOCUS[f"gen-{i}"]
    return rule_checks(r, BUSINESSES[r["meta"]["business_id"]])


for name, ok in [
        ("rule 48: «سلامتك» for a price complaint is flagged (focus 00192)",
         any("سلامتك" in f for f in focus_checks("00192")[1])),
        ("rule 48: «سلامتك» after «توعقت» (unwell) is not flagged (focus 00202)",
         not any("سلامتك" in f for f in focus_checks("00202")[1])),
        ("rule 48: «آسفة» is flagged (focus 00062)", any("آسفين" in f for f in focus_checks("00062")[1])),
        ("confirmation «الأربعاء 31 مارس» for a Thursday 1 April booking fails (focus 00228)",
         any("confirms the booking" in p for p in focus_checks("00228")[0])),
        ("«تم إلغاء موعدك يا سعد» with no name given fails (focus 00224)",
         any("never gave" in p for p in focus_checks("00224")[0])),
        ("«ما نقدر نلغي» is flagged when the policy says free cancellation (focus 00132)",
         any("cancellation limit" in f for f in focus_checks("00132")[1])),
        ("two slot lookups for the same service and day in one turn are flagged (focus 00279)",
         any("two slot lookups" in f for f in focus_checks("00279")[1])),
        ("teacher rule 48: «سلامتك» only for illness, otherwise «آسفين على اللي صار»",
         "«آسفين على اللي صار»" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
TRAIN = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "train" / "train_v1.jsonl").read_text(encoding="utf-8").splitlines()}


def train_checks(i: str) -> tuple[list[str], list[str]]:
    r = TRAIN[f"gen-{i}"]
    return rule_checks(r, BUSINESSES[r["meta"]["business_id"]])


for name, ok in [
        ("«وبعدها ما نقدر نلغيه مجاناً» (the policy restated) is not flagged (train 00238)",
         not any("cancellation limit" in f for f in train_checks("00238")[1])),
        ("«وبعدها ما نقدر نلغي» (no «مجاناً») is still flagged (train 00725)",
         any("cancellation limit" in f for f in train_checks("00725")[1])),
        ("working hours in a confirmation are not the booking's day (train 01167)",
         not any("confirms the booking" in p for p in train_checks("01167")[0])),
        ("the cancelled old booking's day in a confirmation is fine (train 00103)",
         not any("confirms the booking" in p for p in train_checks("00103")[0])),
        ("searching after a time, then the whole day, is not flagged (train 00052)",
         not any("two slot lookups" in f for f in train_checks("00052")[1]))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
expect("«للأسف» (unfortunately) is not a singular apology", record([USER] + SLOTS + [reply("للأسف ما فيه، فيه 4 ونص المسا")]), True)
expect("«يا هلا» is not a name", record([USER, reply("يا هلا، وش تبي؟")]), True)
expect("«يا نورة» after the customer said «اسمي نورة» passes",
       record([{"role": "user", "content": "اسمي نوره"}, reply("أبشري يا نورة")]), True)
from datagen import spoken_clock  # noqa: E402
for minutes, formal, want in [(15 * 60 + 30, False, "3 ونص المسا"), (15 * 60, True, "3 المساء"), (12 * 60, False, "12 المسا")]:
    ok = spoken_clock(minutes, formal) == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} prayer-word repair writes {minutes // 60}:{minutes % 60:02d} as «{want}»")
# the customer simulator (no API call): a slip is written again
from datagen import customer_system, simulator_slip  # noqa: E402
CANCEL_SC = {"kind": "cancel", "goal": "Cancel", "business": GYM,
             "customer": {"gender": "male", "hindi_digits": False, "typos": False, "english_words": False, "emoji": False}}
INFO_SC = {**CANCEL_SC, "kind": "info"}
DONE = ["Customer: ابي الغي حجزي", "Receptionist: تم إلغاء حصة الرياضيات الأربعاء"]
for name, ok in [
        ("simulator: «إيه، الغيه» after a done cancellation is a slip (gen-00810)", simulator_slip("إيه، الغيه. شكراً", CANCEL_SC, DONE) is not None),
        ("simulator: «إيه، الغيه» with nothing to cancel is a slip (gen-00856)", simulator_slip("إيه، الغيه. شكراً", INFO_SC, ["Receptionist: تبين ألغي لك موعد؟"]) is not None),
        ("simulator: «إيه، الغيه» before the cancellation is fine", simulator_slip("إيه، الغيه", CANCEL_SC, ["Receptionist: تبيني ألغيه لك؟"]) is None),
        ("simulator: «أبشر» from the customer is a slip (gen-00843)", simulator_slip("أبشر، أبغى غسيل داخلي", INFO_SC, []) is not None),
        ("simulator: «يعطيك العافية» is fine", simulator_slip("يعطيك العافية", INFO_SC, []) is None),
        ("simulator: «وابشرك حجزت» is a slip (batch 12 gen-01166)", simulator_slip("اسمي نورة، وابشرك حجزت", INFO_SC, []) is not None),
        ("simulator: «الله يبشرك بالخير» is fine", simulator_slip("الله يبشرك بالخير", INFO_SC, []) is None),
        ("simulator: only a cancel customer is told «إيه، الغيه»", "الغيه" in customer_system(CANCEL_SC, [])
         and "الغيه" not in customer_system(INFO_SC, [])),
        ("simulator: after a done cancellation it is told not to confirm again", "already done" in customer_system(CANCEL_SC, DONE)),
        ("teacher rule 11 strict: no prayer time, even as a period", "Never name a prayer time" in teacher_rules("casual", GYM, "هلا")),
        # batch 10 gen-00918, gen-00964: the teacher copied the example «بعد 3 ونص المسا» whatever its `after` was
        ("teacher rule 11 gives no clock example to copy", "«بعد 3" not in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
expect("«بقول لهم» with no handoff call fails (gen-00723)", record([USER, reply("أبشر، بقول لهم إنك تبي تعويض")]), False, reason="without calling handoff")
expect("«بقولهم» with no handoff call fails", record([USER, reply("أبشر، بقولهم")]), False, reason="without calling handoff")
expect("«بقول لهم» in the turn that calls handoff passes", record([USER] + H + [reply("أبشر، بقول لهم إنك تبي تعويض")]), True)
expect("«بقول لك» (to the customer) passes", record([USER] + SLOTS + [reply("بقول لك المتاح: 4 ونص المسا أو 6 المسا")]), True)
# the banned words are not quoted to the teacher: quoting them seemed to prime it (batch 09: 3 × «يا طيب»)
for name, ok in [("teacher rule 44 describes, without quoting, «يا طيب»", "pet name" in teacher_rules("casual", GYM, "هلا")
                  and "يا طيب" not in teacher_rules("casual", GYM, "هلا")),
                 ("teacher rule 45: check before saying available", "before get_available_slots returned it" in teacher_rules("casual", GYM, "هلا")),
                 ("teacher rule 46: a repeated «إيه، الغيه» is not a new instruction", "تقصد ألغي لك" in teacher_rules("casual", GYM, "هلا"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# rule 34: the list repair puts 3+ options one per line and changes nothing else
from datagen import repair_lists  # noqa: E402
for before, after in [
        ("المتاح: 4 المسا، 6 المسا، و7 المسا. أي وقت يناسبك؟", "المتاح:\n4 المسا\n6 المسا\n7 المسا.\nأي وقت يناسبك؟"),
        ("تبغى أي خدمة؟ عندنا تنظيف مكيف، فحص وإصلاح، وتعبئة فريون.", "تبغى أي خدمة؟\nعندنا\nتنظيف مكيف\nفحص وإصلاح\nتعبئة فريون."),
        ("1 ونص، 3 ونص، 6 ونص، 7.", "1 ونص\n3 ونص\n6 ونص\n7."),
        ("فيه 4 المسا أو 7 المسا", "فيه 4 المسا أو 7 المسا"),                        # two options stay in one sentence
        ("المتاح: 9، 10، أو 11", "المتاح: 9، 10، أو 11"),                             # «أو» is not a separator we drop
        ("كشف بيطري، الثلاثاء 26 يناير، 11 الصباح.", "كشف بيطري، الثلاثاء 26 يناير، 11 الصباح."),  # a summary, not options
        ("عندك حجز واحد: كشف بيطري، الثلاثاء 26 يناير، 11 الصباح.", "عندك حجز واحد: كشف بيطري، الثلاثاء 26 يناير، 11 الصباح."),
        ("ما عندنا خدمة زيارة للبيت، الحجز عندنا داخل المطعم بس، وفيه جلسة عائلية خاصة إذا تبي.",
         "ما عندنا خدمة زيارة للبيت، الحجز عندنا داخل المطعم بس، وفيه جلسة عائلية خاصة إذا تبي."),
        ("- بكرة الثلاثاء، الساعة 1 ونص، قاعة صغيرة", "- بكرة الثلاثاء، الساعة 1 ونص، قاعة صغيرة")]:
    got = repair_lists(before)
    failures += got != after
    print(f"{'ok  ' if got == after else 'FAIL'} list repair «{before[:45]}»" + ("" if got == after else f" -> {got!r}"))
# the emoji repair removes only disallowed emojis and the space they leave
from datagen import repair_emojis  # noqa: E402
for before, last, on, after in [("حياك الله 🌿\nتفضل", "", True, "حياك الله\nتفضل"),
                                 ("🙏 أبشر", "", True, "أبشر"),
                                 ("أهلين 🙋‍♀️ وش تبي؟", "", True, "أهلين، وش تبي؟"),
                                 ("حياك 🌸 عندك حجزين", "", True, "حياك، عندك حجزين"),
                                 ("حياك الله 🌿، وش تبي؟", "", True, "حياك الله، وش تبي؟"),
                                 ("تم الحجز ✅🌟", "", True, "تم الحجز ✅"),
                                 ("الله يعافيك 🌸🌸", "شكرا", True, "الله يعافيك 🌸"),
                                 ("حياك الله 🌸", "", True, "حياك الله"),
                                 ("تم الحجز ✅", "", False, "تم الحجز")]:
    got = repair_emojis(before, last, on)
    failures += got != after
    print(f"{'ok  ' if got == after else 'FAIL'} repair «{before}» -> «{got}»")
# 1g: opener classification
for text, want in [("وعليكم السلام ورحمة الله، هلا والله", "هلا والله"), ("يا هلا", "يا هلا"), ("حياك الله، تفضل", "حياك الله"),
                   ("أهلين", "أهلين")]:
    got = opener({"messages": [USER, reply(text)]})
    failures += got != want
    print(f"{'ok  ' if got == want else 'FAIL'} opener of «{text}» is «{got}»")

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
