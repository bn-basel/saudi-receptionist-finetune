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
# rule 11: formal time words are الصباح / الظهر / العصر / المساء
expect("formal «4 ونص العصر» passes (was rejected before decisions_v3)", record([USER] + SLOTS + [reply("حياك الله، متاح 4 ونص العصر")], "formal"), True)
expect("formal «6 المسا» fails (casual word)", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المسا")], "formal"), False, reason="casual time words")
expect("formal «6 المساء» passes", record([USER] + SLOTS + [reply("حياك الله، متاح 6 المساء")], "formal"), True)
# 1b: exact times
expect("slot 16:30 written «4 العصر» fails", record([USER] + SLOTS + [reply("عندنا 4 العصر")]), False, reason="time not from a tool")
expect("slot 16:30 written «4 ونص العصر» passes", record([USER] + SLOTS + [reply("عندنا 4 ونص العصر")]), True)
expect("slot written «16:30» passes", record([USER] + SLOTS + [reply("عندنا 16:30 أو 18:00")]), True)
expect("slot 18:00 written «6 المسا» passes", record([USER] + SLOTS + [reply("عندنا 6 المسا")]), True)
expect("opening hour in an info reply passes", record([{"role": "user", "content": "متى تفتحون"}, reply("نفتح 4 العصر")]), True)
expect("opening hour while offering slots fails", record([USER] + SLOTS + [reply("عندنا 4 العصر أو 6 المسا")]), False)
expect("stated opening hour while offering slots passes (pilot_v2 gen-00006)",
       record([USER] + SLOTS + [reply("نفتح 4 العصر، والمتاح 4 ونص العصر")]), True)
expect("a slot time inside an hours clause must still be an hour", record([USER] + SLOTS + [reply("نفتح 5 العصر")]), False)
# 1c: days against the clock (now = Thursday 5 Nov)
expect("«اليوم الجمعة» on a Thursday fails", record([USER, reply("اليوم الجمعة مسكرين")]), False, reason="«اليوم»")
expect("«اليوم الخميس» passes", record([USER, reply("اليوم الخميس عندنا مواعيد")]), True)
expect("«بكرة السبت» on a Thursday fails", record([USER, reply("بكرة السبت فيه")]), False)
expect("«السبت بعد بكره» passes", record([USER, reply("السبت بعد بكره ما فيه")]), True)
expect("«الخميس 6 نوفمبر» fails (it is a Friday)", record([USER] + SLOTS + [reply("الخميس 6 نوفمبر فيه 4 ونص العصر")]), False, reason="6/11")
expect("«الجمعة 6 نوفمبر» passes", record([USER] + SLOTS + [reply("الجمعة 6 نوفمبر فيه 4 ونص العصر")]), True)
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
expect("«سجلت حجزك» right after create_booking passes", record([USER] + SLOTS + BOOK + [reply("سجلت حجزك 4 ونص العصر")]), True)
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
# rule 11: the time-of-day word fits the hour (Asr 15:00, Maghrib 17:15, Isha 18:45)
expect("noon slot written «12 المساء» fails", record([USER] + NOON + [reply("فيه 12 المساء")], "formal"), False, GYM, reason="does not fit")
expect("noon slot written «12 الظهر» passes", record([USER] + NOON + [reply("فيه 12 الظهر")], "formal"), True, GYM)
expect("13:30 written «1 ونص العصر» fails (pilot_v2 gen-00006)", record([USER] + NOON + [reply("فيه 1 ونص العصر")]), False, GYM, reason="does not fit")
expect("13:30 written «1 ونص الظهر» passes", record([USER] + NOON + [reply("فيه 1 ونص الظهر")]), True, GYM)
expect("21:00 written «9 الليل» passes (casual)", record([USER] + NOON + [reply("فيه 9 الليل")]), True, GYM)
expect("21:00 written «9 الصبح» fails", record([USER] + NOON + [reply("فيه 9 الصبح")]), False, GYM, reason="does not fit")
expect_flag("14:30 «العصر» (30 min before Asr) is a flag, not a reject",
            record([USER] + tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"},
                                 {"date": "2026-11-06", "slots": ["14:30"]}) + [reply("فيه 2 ونص العصر")]), "near a boundary", GYM)
# evening words from 17:00, or from Maghrib minus 90 minutes if earlier; no tolerance before that
LATE = {"Asr": "15:40", "Maghrib": "18:30", "Isha": "20:00"}
EVENING = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"},
               {"date": "2026-11-06", "slots": ["16:30", "17:00"]})
expect("17:00 «5 المساء» with Maghrib 18:30 passes", record([USER] + EVENING + [reply("فيه 5 المساء")], "formal", prayer=LATE), True, GYM)
expect("16:30 «4 ونص المساء» with Maghrib 18:30 fails", record([USER] + EVENING + [reply("فيه 4 ونص المساء")], "formal", prayer=LATE),
       False, GYM, reason="does not fit")
expect("16:30 «4 ونص المساء» with Maghrib 17:15 passes (from 15:45)", record([USER] + EVENING + [reply("فيه 4 ونص المساء")], "formal"),
       True, GYM)
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
expect("16:45 written «5 الا ربع العصر» passes", record([USER] + NOON + [reply("فيه 5 الا ربع العصر")]), True, GYM)
expect("16:45 written «4 وربع العصر» fails", record([USER] + NOON + [reply("فيه 4 وربع العصر")]), False, GYM, reason="time not from a tool")
TWO_DAYS = tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-06"}, {"date": "2026-11-06", "slots": ["12:00"]}) + \
    tool("get_available_slots", {"service_id": "yoga", "date": "2026-11-07"}, {"date": "2026-11-07", "slots": ["12:30"]}, 2)
expect("Friday's 12:00 written «بكرة الجمعة 12 ونص» fails (pilot_v2 gen-00019)",
       record([USER] + TWO_DAYS + [reply("بكرة الجمعة 12 ونص الظهر، وبعده السبت 12 ونص الظهر")]), False, GYM, reason="not a slot on Fri")
expect("each day with its own slot passes", record([USER] + TWO_DAYS + [reply("بكرة الجمعة 12 الظهر، وبعده السبت 12 ونص الظهر")]), True, GYM)
expect("a time just before its day name passes", record([USER] + TWO_DAYS + [reply("الجمعة 12 الظهر، و12 ونص الظهر السبت")]), True, GYM)
# placeholder names, «محجوز لك» before a booking
PLACEHOLDER = tool("create_booking", {"service_id": "cleaning", "date": "2026-11-06", "time": "16:30", "customer_name": "غير معروف"},
                   {"booking_id": "B-1", "status": "confirmed"}, 2)
expect("create_booking with «غير معروف» fails (pilot_v2 gen-00037)", record([USER] + SLOTS + PLACEHOLDER + [reply("تم")]), False, reason="placeholder")
expect("«محجوز لك» before create_booking fails (pilot_v2 gen-00000)", record([USER] + SLOTS + [reply("4 ونص العصر محجوز لك")]), False, reason="محجوز لك")
expect("«محجوز لك» after create_booking passes", record([USER] + SLOTS + BOOK + [reply("4 ونص العصر محجوز لك")]), True)
expect("«كله محجوز» (fully booked) passes", record([USER] + SLOTS + [reply("الصبح كله محجوز، فيه 4 ونص العصر")]), True)
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
# 1g: opener classification
for text, want in [("وعليكم السلام ورحمة الله، هلا والله", "هلا والله"), ("يا هلا", "يا هلا"), ("حياك الله، تفضل", "حياك الله"),
                   ("أهلين", "أهلين")]:
    got = opener({"messages": [USER, reply(text)]})
    failures += got != want
    print(f"{'ok  ' if got == want else 'FAIL'} opener of «{text}» is «{got}»")

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
