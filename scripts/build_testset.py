"""Stage 4: build, check and freeze the test and dev sets.

  sheet    Write data/test/sheet_v1.csv for native-speaker review (never overwrites it;
           add --force to start over). Opens in Excel with Arabic intact.
  build    Read the drafts and the reviewed sheet, assemble every case with the fake
           backend, validate, write data/test/{test,dev}_v1.jsonl, print the balance.
  freeze   Record the SHA-256 fingerprints of both files in docs/TEST_SET.md.

Run: uv run python scripts/build_testset.py sheet|build|freeze
"""

import csv
import hashlib
import itertools
import json
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

from backend import Backend, resolve_day, to_min
from prompt import WEEKDAYS_AR, load_spec
from testset_drafts import CATEGORIES, NOW

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "test"
SHEET = OUT / "sheet_v1.csv"
FILES = {"test": OUT / "test_v1.jsonl", "dev": OUT / "dev_v1.jsonl"}
TEXT_FIELDS = ["customer_1", "assistant_1", "customer_2"]
PROVENANCE = "synthetic drafts, reviewed and edited by a native speaker"

BUSINESS = {"C": "dental_clinic", "S": "salon", "W": "car_wash", "R": "restaurant"}
PRAYER = {  # plausible early-October times per city
    "الرياض": {"Asr": "15:12", "Maghrib": "17:41", "Isha": "19:11"},
    "جدة": {"Asr": "15:27", "Maghrib": "18:02", "Isha": "19:32"},
    "الدمام": {"Asr": "14:57", "Maghrib": "17:26", "Isha": "18:56"},
}
STYLES = [dict(register=r, warmth=w, emoji=e)
          for r, w, e in itertools.product(["casual", "formal"], ["warm", "plain"], ["on", "off"])]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿‍️]")
MOJIBAKE = re.compile("[ÃØÙ][\u0080-ÿ]")


def fmt_time(hhmm: str) -> str:
    """20:30 -> '8 ونص الليل', the way times are written in Saudi WhatsApp."""
    h, m = map(int, hhmm.split(":"))
    part = ("الصبح" if 5 <= h < 12 else "الظهر" if h < 15 else "العصر" if h < 18
            else "المسا" if h < 20 else "الليل")
    h12 = h % 12 or 12
    return f"{h12}{' ونص' if m == 30 else ''} {part}"


class Case:
    """Builds one case: context messages with real backend results, plus the expectation."""

    def __init__(self, business: dict, meta: dict):
        self.backend = Backend(business, meta)
        self.messages: list[dict] = []
        self.n = 0

    def user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def tool(self, name: str, args: dict) -> dict:
        self.n += 1
        call_id = f"call_{self.n}"
        result = self.backend.call(name, args)
        if "error" in result:
            raise ValueError(f"backend error in context: {name}{args} -> {result}")
        self.messages.append({"role": "assistant", "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}]})
        self.messages.append({"role": "tool", "tool_call_id": call_id, "name": name,
                              "content": json.dumps(result, ensure_ascii=False)})
        return result


def expect_tool(name, exact=None, nonempty=None, args_in=None, label="correct"):
    return {"label": label, "kind": "tool_call", "tool": name, "args_exact": exact or {},
            "args_nonempty": nonempty or [], "args_in": args_in or {}}


def expect_reply(label="correct", must_include_any=None, must_not_include=None):
    return {"label": label, "kind": "reply", "no_invented_numbers": True,
            "must_include_any": must_include_any or [], "must_not_include": must_not_include or []}


def open_days(business: dict, today: date, exclude: date | None = None) -> list[str]:
    days = [resolve_day(today, f"+{k}") for k in range(0, 8)]
    return [str(d) for d in days if d != exclude
            and business["schedule"][["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()]]]


def build_case(cat: str, d: dict, business: dict, now: datetime, text: dict) -> tuple[list, list, str, dict]:
    """Returns (messages, expect options, situation text, extra meta)."""
    today = now.date()
    svc_name = lambda sid: next(s["name"] for s in business["services"] if s["id"] == sid)
    meta: dict = {}
    if "slots" in d:
        meta["slot_overrides"] = {str(resolve_day(today, d["day"])): d["slots"]}
    bookings, new_date = [], None
    for k, (sid, day, t) in enumerate(d.get("bookings", [d["booking"]] if "booking" in d else [])):
        bookings.append({"booking_id": f"B-{2000 + k + 1}", "service_id": sid,
                         "date": str(resolve_day(today, day)), "time": t})
    if bookings:
        meta["customer_bookings"] = bookings
    if cat == "unseen_tool":
        new_date = str(resolve_day(today, d["day"]))
        t = to_min(d["new"])
        extra = t + 60 if t + 60 <= 22 * 60 + 30 else t - 60  # a second free slot, one hour away
        meta["slot_overrides"] = {new_date: sorted({d["new"], f"{extra // 60:02d}:{extra % 60:02d}"})}

    c = Case(business, meta)
    c1 = text["customer_1"]
    fill = lambda s, **kw: s.format(**kw) if s else s
    target = str(resolve_day(today, d["day"])) if "day" in d and cat != "unseen_tool" else None

    if cat == "price":
        c.user(c1)
        exp = [expect_tool("search_services", nonempty=[] if d.get("generic") else ["query"])]
        sit = "Asks a price/duration. Next: search_services."
    elif cat in ("booking", "after_slots", "agree", "closed"):
        c.user(c1)
        c.tool("search_services", {"query": svc_name(d["svc"])})
        if cat == "booking":
            exp = [expect_tool("get_available_slots", exact={"service_id": d["svc"], "date": target})]
            sit = f"Wants {d['svc']} on {target} ('{d['day']}' from {now:%a %Y-%m-%d %H:%M}). Next: get_available_slots({d['svc']}, {target})."
        elif cat == "closed":
            ok_days = open_days(business, today, exclude=None)
            exp = [expect_reply(label="explains_hours"),
                   expect_tool("get_available_slots", exact={"service_id": d["svc"]},
                               args_in={"date": ok_days}, label="checks_open_day")]
            sit = f"Asks for {d['svc']} at a closed day/time (around {target}). Next: explain hours, or check an open day."
        else:
            c.tool("get_available_slots", {"service_id": d["svc"], "date": target})
            t1, t2 = d["slots"][0], d["slots"][1] if len(d["slots"]) > 1 else d["slots"][0]
            if cat == "after_slots":
                exp = [expect_reply()]
                sit = f"Wants {d['svc']} on {target}; free: {', '.join(d['slots'])}. Next: offer only these times, do not book yet."
            else:
                c.assistant(fill(text["assistant_1"], t1=fmt_time(t1), t2=fmt_time(t2)))
                c.user(fill(text["customer_2"], t1=fmt_time(t1), t2=fmt_time(t2)))
                picked = d["slots"][d["pick"] - 1]
                exp = [expect_tool("create_booking", exact={"service_id": d["svc"], "date": target,
                                                            "time": picked, "customer_name": d["name"]})]
                sit = f"Offered {', '.join(d['slots'])} on {target}; customer picks {picked}, name {d['name']}. Next: create_booking."
    elif cat == "cancel":
        c.user(c1)
        if d["step"] == 1:
            exp = [expect_tool("get_my_bookings")]
            sit = "Wants to cancel. Next: get_my_bookings."
        else:
            c.tool("get_my_bookings", {})
            desc = [f"{svc_name(b['service_id'])} يوم {WEEKDAYS_AR[date.fromisoformat(b['date']).weekday()]} الساعة {fmt_time(b['time'])}"
                    for b in bookings]
            if d["step"] == 2:
                exp = [expect_reply()]
                sit = f"Wants to cancel; has 2 bookings ({bookings[0]['service_id']}, {bookings[1]['service_id']}). Next: ask which one, do not cancel yet."
            else:
                c.assistant(fill(text["assistant_1"], b1=desc[0], b2=desc[1]))
                c.user(text["customer_2"])
                chosen = bookings[d["pick"] - 1]
                exp = [expect_tool("cancel_booking", exact={"booking_id": chosen["booking_id"]})]
                sit = f"Has 2 bookings; picks {chosen['service_id']} ({chosen['booking_id']}). Next: cancel_booking."
    elif cat == "info":
        c.user(c1)
        exp = [expect_reply(must_include_any=[business["map_link"]] if d.get("location") else None)]
        sit = "Asks something in the business info" + (" (location: send the map link)" if d.get("location") else "") + ". Next: reply, no tool."
    elif cat in ("unknown", "complaint"):
        c.user(c1)
        exp = [expect_tool("handoff_to_human", nonempty=["reason"])]
        sit = ("Asks something NOT in the info or tools" if cat == "unknown"
               else "Complaint, emergency or wants a person") + ". Next: handoff_to_human."
    elif cat == "smalltalk":
        c.user(c1)
        exp = [expect_reply()]
        sit = "Small talk / thanks / off-topic. Next: short friendly reply, no tool."
    elif cat == "unseen_tool":
        c.user(c1)
        c.tool("get_my_bookings", {})
        b = bookings[0]
        c.tool("get_available_slots", {"service_id": b["service_id"], "date": new_date})
        exp = [expect_tool("reschedule_booking", exact={"booking_id": b["booking_id"], "date": new_date, "time": d["new"]},
                           label="uses_new_tool"),
               expect_tool("cancel_booking", exact={"booking_id": b["booking_id"]}, label="old_pattern")]
        sit = f"Has {b['service_id']} on {b['date']} {b['time']}; wants {new_date} {d['new']} (free). Next: reschedule_booking (a tool never seen in training)."
    elif cat == "pressure":
        if d.get("ctx"):
            c.user(c1)
            c.tool("search_services", {"query": svc_name(d["ctx"])})
        else:
            c.user(c1)
        options = d["expect"]["any"] if "any" in d["expect"] else [d["expect"]]
        exp = []
        for o in options:
            if o.get("reply"):
                exp.append(expect_reply(must_not_include=o.get("must_not_include")))
            elif o["tool"] == "get_available_slots":
                exp.append(expect_tool(o["tool"], exact={"service_id": d["ctx"], "date": str(resolve_day(today, o["day"]))}))
            elif o["tool"] in ("search_services", "handoff_to_human"):
                exp.append(expect_tool(o["tool"], nonempty=["reason"] if o["tool"] == "handoff_to_human" else []))
            else:
                exp.append(expect_tool(o["tool"]))
        for i, e in enumerate(exp):
            e["label"] = "correct" if len(exp) == 1 else f"acceptable_{i + 1}"
        sit = "Pressure test. Next: " + " OR ".join(e.get("tool", "reply (no tool)") for e in exp) + "."
    else:
        raise ValueError(cat)
    return c.messages, exp, sit, meta


def drafts():
    """Yield (id, split, category, draft) in a fixed order with fixed dev picks."""
    for cat, cases, n_dev in CATEGORIES:
        dev = set(random.Random(f"dev-{cat}").sample(range(len(cases)), n_dev))
        for i, d in enumerate(cases):
            yield f"{cat}-{i + 1:02d}", ("dev" if i in dev else "test"), cat, d


def text_fields(d: dict) -> dict:
    return {"customer_1": d.get("c1", ""), "assistant_1": d.get("a1", ""), "customer_2": d.get("c2", "")}


def read_sheet() -> dict:
    if not SHEET.exists():
        return {}
    with SHEET.open(encoding="utf-8-sig", newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def assemble():
    businesses, _, tools = load_spec()
    by_id = {b["id"]: b for b in businesses}
    sheet = read_sheet()
    now_keys = list(NOW)
    cases, problems = [], []
    for n, (cid, split, cat, d) in enumerate(drafts()):
        business = by_id[BUSINESS[d["b"]]]
        now = datetime.fromisoformat(NOW[d.get("now") or now_keys[n % len(now_keys)]])
        style = STYLES[n % len(STYLES)]
        text = text_fields(d)
        if cid in sheet:
            text.update({k: sheet[cid][k].strip() for k in TEXT_FIELDS if sheet[cid].get(k, "").strip()})
        for k, v in text.items():
            if MOJIBAKE.search(v):
                problems.append(f"{cid}: {k} looks garbled (was the CSV saved as 'CSV UTF-8'?)")
            if style["emoji"] == "off" and k == "assistant_1":
                text[k] = EMOJI.sub("", v).strip()
        try:
            messages, expect, situation, extra = build_case(cat, d, business, now, text)
        except (ValueError, KeyError, IndexError) as e:
            problems.append(f"{cid}: {e}")
            continue
        for e in expect:
            if e["kind"] == "tool_call":
                names = {t["function"]["name"] for t in tools} | {"reschedule_booking"}
                if e["tool"] not in names:
                    problems.append(f"{cid}: unknown expected tool {e['tool']}")
        for m in messages:
            if m.get("content") is not None and "{" in m["content"] and m["role"] != "tool":
                problems.append(f"{cid}: unfilled placeholder in {m['content']!r}")
        meta = {"business_id": business["id"], "style": style, "now": now.strftime("%Y-%m-%dT%H:%M"),
                "prayer_times": PRAYER[business["city"]], **extra}
        cases.append({
            "id": cid, "split": split, "category": cat, "meta": meta,
            "tools": "default+unseen" if cat == "unseen_tool" else "default",
            "messages": messages, "expect": {"options": expect},
            "dialect_review": split == "test" and cat in ("after_slots", "info", "smalltalk"),
            "situation": situation, "provenance": PROVENANCE,
        })
    return cases, problems


def cmd_sheet(force: bool) -> None:
    if SHEET.exists() and not force:
        sys.exit(f"{SHEET} already exists (it may contain your edits). Use --force to overwrite.")
    cases, problems = assemble()
    by_id = {c["id"]: c for c in cases}
    OUT.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "category", "business", "style", "situation", *TEXT_FIELDS, "note"])
        for cid, split, cat, d in drafts():
            c = by_id.get(cid)
            style = "/".join(c["meta"]["style"].values()) if c else ""
            w.writerow([cid, split, cat, BUSINESS[d["b"]], style, c["situation"] if c else "",
                        *text_fields(d).values(), ""])
    print(f"wrote {SHEET} ({len(cases)} cases)")
    for p in problems:
        print("PROBLEM:", p)


def cmd_build() -> None:
    cases, problems = assemble()
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        sys.exit(f"{len(problems)} problem(s): nothing written.")
    for split, path in FILES.items():
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases if c["split"] == split),
                        encoding="utf-8")
    print(f"wrote {FILES['test'].name} and {FILES['dev'].name}\n")
    table = {}
    for c in cases:
        table.setdefault(c["category"], {"test": 0, "dev": 0})[c["split"]] += 1
    print(f"{'category':12s} test dev")
    for cat, n in table.items():
        print(f"{cat:12s} {n['test']:4d} {n['dev']:3d}")
    print(f"{'total':12s} {sum(n['test'] for n in table.values()):4d} {sum(n['dev'] for n in table.values()):3d}")
    for key, get in [("business", lambda c: c["meta"]["business_id"]),
                     ("style", lambda c: "/".join(c["meta"]["style"].values()))]:
        counts = {}
        for c in cases:
            if c["split"] == "test":
                counts[get(c)] = counts.get(get(c), 0) + 1
        print(f"\ntest cases per {key}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"\ndialect-review cases: {sum(c['dialect_review'] for c in cases)}")


def cmd_freeze() -> None:
    doc = ROOT / "docs" / "TEST_SET.md"
    text = doc.read_text(encoding="utf-8")
    today = date.today().isoformat()
    for split, path in FILES.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        text = re.sub(rf"\| `data/test/{path.name}` \| [^|]+ \| [^|]* \|",
                      f"| `data/test/{path.name}` | `{digest}` | {today} |", text)
        print(f"{path.name}: {digest}")
    doc.write_text(text, encoding="utf-8")
    print(f"recorded in {doc}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "sheet":
        cmd_sheet("--force" in sys.argv)
    elif command == "build":
        cmd_build()
    elif command == "freeze":
        cmd_freeze()
    else:
        sys.exit(__doc__)
