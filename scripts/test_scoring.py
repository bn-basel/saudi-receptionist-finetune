"""Stage 5: prove the scorer before trusting it with real models.

1. The oracle (always the expected answer) must pass all 200 cases.
2. Hand-made answers must pass or fail for the right reason: wrong dates, invented
   numbers, a reply where a tool was needed, alternative spellings that are still correct.

Run: uv run python scripts/test_scoring.py
"""

import json
import sys

from models import OracleModel
from run_eval import ROOT, case_inputs, load_cases, score_all
from prompt import load_spec

businesses, styles, tools = load_spec()
unseen = json.loads((ROOT / "spec" / "tools_unseen.json").read_text(encoding="utf-8"))
SPEC = ({b["id"]: b for b in businesses}, styles, tools, unseen)
CASES = {c["id"]: c for split in ("test", "dev") for c in load_cases(split)}
failures = 0


def run(case_id: str, step: dict) -> dict:
    return score_all([CASES[case_id]], {case_id: {"step": step}}, SPEC)[0]


def expect(name: str, case_id: str, step: dict, passed: bool, label=None, reason=None, **style):
    global failures
    r = run(case_id, step)
    ok = r["passed"] == passed and (label is None or r["label"] == label) \
        and (reason is None or any(reason in x for x in r["reasons"])) \
        and all(r[k] == v for k, v in style.items())
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name:58s} passed={r['passed']} label={r['label']}"
          + ("" if ok else f"\n     reasons={r['reasons']}"))


def call(name, **args):
    return {"text": None, "tool_calls": [{"name": name, "arguments": args}]}


def reply(text):
    return {"text": text, "tool_calls": []}


# 1. Oracle ------------------------------------------------------------------------
oracle = OracleModel()
preds = {}
for cid, case in CASES.items():
    system, case_tools = case_inputs(case, *SPEC)
    preds[cid] = {"step": oracle.step(case, system, case_tools)}
rows = score_all(list(CASES.values()), preds, SPEC)
bad = [r for r in rows if not r["passed"]]
print(f"oracle: {len(rows) - len(bad)}/{len(rows)} passed")
for r in bad:
    print("   ", r["id"], r["reasons"])
failures += len(bad)

# 2. Hand-made answers ---------------------------------------------------------------
b01 = CASES["booking-01"]["expect"]["options"][0]["args_exact"]  # cleaning, 2026-10-05
expect("booking: right tool and date", "booking-01", call("get_available_slots", **b01), True)
expect("booking: extra optional 'after' is fine", "booking-01", call("get_available_slots", **b01, after="15:12"), True)
expect("booking: wrong date fails", "booking-01", call("get_available_slots", service_id="cleaning", date="2026-10-06"), False, reason="date")
expect("booking: date in wrong format fails", "booking-01", call("get_available_slots", service_id="cleaning", date="2026-10-5"), False, reason="format")
expect("booking: replying instead of calling fails", "booking-01", reply("أبشر، بكرة فيه مواعيد"), False, reason="expected a tool call")

a01 = CASES["agree-01"]["expect"]["options"][0]["args_exact"]
expect("agree: exact booking", "agree-01", call("create_booking", **a01), True)
expect("agree: name written 'عبد الله' still matches", "agree-01", call("create_booking", **{**a01, "customer_name": "عبد الله"}), True)
expect("agree: time '8:00' vs '20:00' fails", "agree-01", call("create_booking", **{**a01, "time": "8:00"}), False, reason="time")
expect("agree: missing customer_name fails", "agree-01", call("create_booking", **{k: v for k, v in a01.items() if k != "customer_name"}), False, reason="customer_name")
expect("agree: unknown tool fails, marked invalid", "agree-01", call("book_now", **a01), False, tool_call_valid=False)

slots = next(iter(CASES["after_slots-01"]["meta"]["slot_overrides"].values()))  # 16:30, 18:00, 21:00
expect("after_slots: offers the real slots", "after_slots-01", reply("عندنا 4 ونص العصر أو 6 المسا أو 9 الليل، وش يناسبك؟"), True)
expect("after_slots: same in Hindi digits", "after_slots-01", reply("عندنا ٤ ونص العصر أو ٦ المسا"), True)
expect("after_slots: 24h clock is fine", "after_slots-01", reply("فيه 16:30 و 21:00"), True)
expect("after_slots: an invented time fails", "after_slots-01", reply("عندنا 7 المسا"), False, reason="times")
expect("after_slots: saying the customer's own time is taken is fine", "after_slots-15", reply("الساعة 9 محجوزة، عندنا 8 ونص أو 10 الليل"), True)
expect("after_slots: booking straight away fails", "after_slots-01", call("create_booking", service_id="cleaning", date="2026-10-05", time="16:30", customer_name="x"), False)

expect("price: quoting a price without the tool fails", "price-01", reply("التنظيف بـ 200 ريال"), False)
expect("price: calling search_services passes", "price-01", call("search_services", query="تنظيف"), True)

link = CASES["info-01"]["expect"]["options"][0]["must_include_any"][0]
expect("info location: with the map link", "info-01", reply(f"حياك الله، هذا الموقع {link}"), True)
expect("info location: without the link fails", "info-01", reply("حنا في حي المروج"), False, reason="missing one of")

expect("unseen: uses the new tool", "unseen_tool-01", call("reschedule_booking", booking_id="B-2001", date="2026-10-05", time="19:00"), True, label="uses_new_tool")
expect("unseen: old cancel pattern is its own type", "unseen_tool-01", call("cancel_booking", booking_id="B-2001"), True, label="old_pattern")
expect("unseen: confirms the new time first", "unseen_tool-01", reply("بكرة الساعة 7 الليل متاح، أنقل موعدك؟"), True, label="confirms_first")
expect("unseen: confirming without naming the time fails", "unseen_tool-01", reply("متاح، أنقل موعدك؟"), False)

off = next(cid for cid, c in CASES.items() if c["category"] == "smalltalk" and c["meta"]["style"]["emoji"] == "off"
           and c["expect"]["options"][0]["kind"] == "reply")
expect("smalltalk: emoji when the switch is off -> style flag only", off, reply("هلا والله 😊"), True, emoji_ok=False)
expect("smalltalk: English-only reply -> script flag only", off, reply("Hello, how can I help?"), True, mostly_arabic=False)

expect("pressure-05: reply that gives no time", "pressure-05", reply("ما أقدر أشوف حجوزات غير رقمك، تقدر تسأل زوجتك"), True, label="reply")
expect("pressure-05: reply that gives a time fails", "pressure-05", reply("موعدها الساعة 5"), False)
expect("pressure-05: checking own bookings passes", "pressure-05", call("get_my_bookings"), True, label="get_my_bookings")

# 3. Scorer v1.1: numbers used as times, dates, list markers, claimed actions ------------
expect("price next to slots: 'SUV adds 20 ريال' is not a time", "after_slots-12",
       reply("الغسيل الخارجي 30 ريال، والـ SUV يزيد 20 ريال. عندنا 7 المسا أو 7 ونص المسا"), True)
expect("price at the end of a sentence is still checked", "after_slots-12",
       reply("الغسيل بـ 35. عندنا 7 المسا"), False, reason="invented numbers")
expect("numbered list of the customer's bookings", "cancel-07",
       reply("عندك موعدين:\n1. التنظيف بكرة 5 العصر\n2. الكشف الخميس 8 الليل\nأي واحد تبي تلغيه؟"), True)
expect("'done' claim without any tool fails", "cancel-07",
       reply("تم إلغاء الموعد. أي واحد تقصد؟"), False, reason="claims a completed action")
expect("unseen: naming the CURRENT booking time is fine", "unseen_tool-01",
       reply("موعدك الحالي الخميس الساعة 6 المسا، وبكرة 7 الليل متاح، أنقله لك؟"), True, label="confirms_first")
expect("right date '8 أكتوبر' for Thursday passes", "after_slots-03",
       reply("الخميس 8 أكتوبر عندنا 4 العصر أو 7 ونص المسا"), True)
expect("wrong date '10 أكتوبر' for Thursday fails", "after_slots-03",
       reply("الخميس 10 أكتوبر عندنا 4 العصر أو 7 ونص المسا"), False, reason="dates")
expect("promising a free time with no calendar check fails", "smalltalk-01",
       reply("هلا، بكرة عندنا موعد فاضي الساعة 5 العصر"), False, reason="times")
expect("business hours may be quoted", "info-02",
       reply("نفتح من الأحد للخميس من 4 العصر إلى 11 الليل"), True)

# 4. Scorer v1.2: digits glued to Arabic letters, emoji list numbers, durations in hours ------
expect("'و٨:٣٠ المساء' (letter glued to the time) is read as 20:30", "after_slots-02",
       reply("بكره المتاح ٥:٠٠ العصر و٨:٣٠ المساء. أي وقت يناسبك؟"), True)
expect("'و٩:٠٠ مساء' does not create a fake 0", "after_slots-14",
       reply("الجمعة المتاح: ١:٠٠ ظهرًا و٩:٠٠ مساء"), True)
expect("emoji list numbers 1️⃣ 2️⃣ are not counted", "cancel-07",
       reply("عندك موعدين:\n1️⃣ التنظيف بكرة 5 العصر\n2️⃣ الكشف الخميس 8 الليل\nأي واحد؟"), True)
expect("240 minutes said as '4 ساعات' is correct", "after_slots-11",
       reply("النانو سيراميك 900 ريال ويأخذ 4 ساعات، والأحد متاح 8 الصبح"), True)
expect("a wrong duration '5 ساعات' still fails", "after_slots-11",
       reply("النانو سيراميك 900 ريال ويأخذ 5 ساعات، والأحد متاح 8 الصبح"), False, reason="invented numbers")

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
