"""Stage 6: unit tests for the review-rule checks in datagen.rule_checks (no API calls).

Every check gets at least one hand-made reply that must pass and one that must fail.

Run: uv run python scripts/test_datagen.py
"""

import json
import sys
from pathlib import Path

from build_testset import trigrams
from datagen import leak_score, opener, rule_checks, train_tools
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


USER = {"role": "user", "content": "ابي احجز تنظيف بكرة"}
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
expect("formal «4 ونص العصر» fails (decisions_v4)", record([USER] + SLOTS + [reply("حياك الله، متاح 4 ونص العصر")], "formal"), False, reason="not time labels")
expect("formal «6 المسا» fails (casual word)", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المسا")], "formal"), False, reason="casual time words")
expect("formal «6 المساء» passes", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المساء")], "formal"), True)
# 1b: exact times
expect("slot 16:30 written «4 المسا» fails", record([USER] + SLOTS + [reply("عندنا 4 المسا")]), False, reason="time not from a tool")
expect("slot 16:30 written «4 ونص المسا» passes", record([USER] + SLOTS + [reply("عندنا 4 ونص المسا")]), True)
expect("slot written «16:30» passes", record([USER] + SLOTS + [reply("عندنا 16:30 أو 18:00")]), True)
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
expect("«أبشري» after «انا فاضية» passes", record([{"role": "user", "content": "انا فاضية بكرة"}, reply("أبشري")]), True)
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
expect("customer single English word passes", record([{"role": "user", "content": "ابي booking بكرة"}, reply("تمام")]), True)
expect("English scenario allows English sentences", record([{"role": "user", "content": "book a table please"}, reply("تمام")], scenario="english"), True)
# leakage: greetings are exempt, real copied lines are not
TEST_GRAMS = [trigrams("السلام عليكم ورحمة الله"), trigrams("ابي احجز قص شعر للولد بكرة بعد العصر")]
for name, ok in [("greeting identical to a test line is not leakage", leak_score("السلام عليكم ورحمة الله", TEST_GRAMS) == 0),
                 ("a copied test request is leakage", leak_score("ابي احجز قص شعر للولد بكرة بعد العصر", TEST_GRAMS) >= 0.6)]:
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
expect("noon slot written «12 الظهر» fails (not a label)", record([USER] + NOON + [reply("فيه 12 الظهر")], "formal"), False, GYM, reason="not time labels")
expect("13:30 written «1 ونص العصر» fails (not a label)", record([USER] + NOON + [reply("فيه 1 ونص العصر")]), False, GYM, reason="not time labels")
expect("13:30 written «1 ونص المسا» passes (casual)", record([USER] + NOON + [reply("فيه 1 ونص المسا")]), True, GYM)
expect("noon slot written «12 الصبح» fails", record([USER] + NOON + [reply("فيه 12 الصبح")]), False, GYM, reason="does not fit")
expect("21:00 written «9 الليل» passes (casual)", record([USER] + NOON + [reply("فيه 9 الليل")]), True, GYM)
expect("21:00 written «9 الصبح» fails", record([USER] + NOON + [reply("فيه 9 الصبح")]), False, GYM, reason="does not fit")
EVENING = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"},
               {"date": "2026-11-06", "slots": ["10:30", "16:30", "18:00", "19:00"]})
expect("10:30 written «10 ونص المسا» fails", record([USER] + EVENING + [reply("فيه 10 ونص المسا")]), False, GYM, reason="does not fit")
expect("16:30 «4 ونص المساء» passes whatever the prayer times", record([USER] + EVENING + [reply("فيه 4 ونص المساء")], "formal",
       prayer={"Asr": "15:40", "Maghrib": "18:30", "Isha": "20:00"}), True, GYM)
expect_flag("19:00 «7 الليل» is a flag, not a reject", record([USER] + EVENING + [reply("فيه 7 الليل")]), "near a boundary", GYM)
expect("18:00 «6 الليل» fails", record([USER] + EVENING + [reply("فيه 6 الليل")]), False, GYM, reason="does not fit")
expect("«بعد العصر» for a period the customer asked about passes",
       record([{"role": "user", "content": "ابي موعد بعد العصر"}] + EVENING + [reply("بعد العصر فيه 4 ونص المسا")]), True, GYM)
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
expect("an English reply to an English customer passes", record([{"role": "user", "content": "Hi, how much is cleaning?"},
                                                                  reply("Cleaning is 200 riyals, it takes one hour.")], scenario="english"), True)
expect("self-talk fails even in an English conversation", record([{"role": "user", "content": "Hi"}, reply("Let me check the rules first. Hello!")],
                                                                  scenario="english"), False, reason="self-talk")
# teacher prompt: the clock rule and the hall deposit line
from datagen import EXAMPLES, teacher_rules  # noqa: E402
EXAMPLES.update({"formal": [], "casual": []})
HALL = BUSINESSES["train_hall_1"]
for name, ok in [("formal teacher rule says «المساء» from 12:00", "«المساء» from 12:00" in teacher_rules("formal", HALL, "x")),
                 ("teacher rule no longer names prayer times", "Asr" not in teacher_rules("casual", GYM, "هلا")),
                 ("hall teacher prompt has the deposit line", "deposit" in teacher_rules("formal", HALL, "x")),
                 ("gym teacher prompt has no deposit line", "deposit to confirm" not in teacher_rules("formal", GYM, "x"))]:
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
# 1g: opener classification
for text, want in [("وعليكم السلام ورحمة الله، هلا والله", "هلا والله"), ("يا هلا", "يا هلا"), ("حياك الله، تفضل", "حياك الله"),
                   ("أهلين", "أهلين")]:
    got = opener({"messages": [USER, reply(text)]})
    failures += got != want
    print(f"{'ok  ' if got == want else 'FAIL'} opener of «{text}» is «{got}»")

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
