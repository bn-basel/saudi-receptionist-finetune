"""Stage 4: build, check and freeze the test and dev sets.

  sheet    Write data/test/sheet_v1.csv for native-speaker review. Never overwrites the
           text columns: --refresh updates only the descriptive columns, --force starts over.
           Opens in Excel with Arabic intact.
  build    Read the drafts and the reviewed sheet, assemble every case with the fake
           backend, validate, write data/test/{test,dev}_v1.jsonl, print the balance.
  check    Validate the built files: tool calls against the spec, near-duplicates,
           overlap with the bake-off and probe messages (scores only), digits, greetings.
  freeze   Record the SHA-256 fingerprints of both files in docs/TEST_SET.md.

Run: uv run python scripts/build_testset.py sheet|build|check|freeze
Add --v2 for test set v2 (docs/TEST_SET_V2.md): drafts from scripts/testset_drafts_v2.py, its own businesses
(spec/test_businesses_v2.json), sheet_v2.csv, a test split only (test_v2.jsonl). Without it, v1 is built exactly
as before.
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

from backend import Backend, normalize_ar, resolve_day, to_min
from prompt import WEEKDAYS_AR, load_spec

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "test"
TEXT_FIELDS = ["customer_1", "assistant_1", "customer_2"]
INFO_FIELDS = ["id", "split", "category", "business", "style", "situation"]
V2 = "--v2" in sys.argv
if V2:
    from testset_drafts_v2 import BUSINESS, CATEGORIES, NOW, PRAYER
    SHEET = OUT / "sheet_v2.csv"
    FILES = {"test": OUT / "test_v2.jsonl"}
    BUSINESS_FILE = ROOT / "spec" / "test_businesses_v2.json"
    DOC = ROOT / "docs" / "TEST_SET_V2.md"
    PROVENANCE = "synthetic drafts by Claude from a native speaker's style picks, reviewed by an AI reviewer following the native speaker's rules"
else:
    from testset_drafts import CATEGORIES, NOW
    SHEET = OUT / "sheet_v1.csv"
    FILES = {"test": OUT / "test_v1.jsonl", "dev": OUT / "dev_v1.jsonl"}
    BUSINESS_FILE = None  # spec/businesses.json, through load_spec()
    DOC = ROOT / "docs" / "TEST_SET.md"
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
TIME_WORDS = re.compile(r"(الصبح|الظهر|العصر|المسا|الليل|الصباح|المساء)")
HINDI_DIGITS = re.compile("[٠-٩]")
ARABIC_DIGITS = re.compile("[0-9]")
LATIN_WORD = re.compile(r"[A-Za-z]+[235679][A-Za-z]+|[235679][A-Za-z]{3,}")  # Arabizi (si3r, a7jiz, 9abgha), not "9pm"


def fmt_hour(hhmm: str) -> str:
    """20:30 -> '8 ونص': the hour only, as a customer would say it (R8)."""
    h, m = map(int, hhmm.split(":"))
    return f"{h % 12 or 12}{' ونص' if m == 30 else ''}"


def fmt_time(hhmm: str, register: str) -> str:
    """The assistant's way to write a time (R1, R13). Arabic digits (0-9).
    formal: 'الصباح' before 12:00, 'المساء' from 12:00. casual: الصبح/الظهر/العصر/المسا/الليل."""
    h = int(hhmm.split(":")[0])
    if register == "formal":
        part = "الصباح" if h < 12 else "المساء"
    else:
        part = ("الصبح" if 5 <= h < 12 else "الظهر" if h < 15 else "العصر" if h < 18
                else "المسا" if h < 20 else "الليل")
    return f"{fmt_hour(hhmm)} {part}"


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


def expect_reply(label="correct", must_include_any=None, must_not_include=None,
                 must_mention_times=None, no_times=False):
    e = {"label": label, "kind": "reply", "no_invented_numbers": True,
         "must_include_any": must_include_any or [], "must_not_include": must_not_include or []}
    if must_mention_times:
        e["must_mention_times"] = must_mention_times  # any spelling: 7, ٧, 7 المساء, 19:00
    if no_times:
        e["no_times"] = True
    return e


def options_from_spec(spec: dict, today: date, ctx_service: str | None) -> list[dict]:
    """Expectation shorthand used in the drafts: {"tool": ...}, {"reply": True, ...} or {"any": [...]}."""
    options = spec["any"] if "any" in spec else [spec]
    out = []
    for o in options:
        if o.get("reply"):
            out.append(expect_reply(must_not_include=o.get("must_not_include"), no_times=o.get("no_times", False)))
        elif o["tool"] == "get_available_slots":
            out.append(expect_tool(o["tool"], exact={"service_id": ctx_service,
                                                    "date": str(resolve_day(today, o["day"]))}))
        elif o["tool"] == "handoff_to_human":
            out.append(expect_tool(o["tool"], nonempty=["reason"]))
        else:
            out.append(expect_tool(o["tool"]))
    for e in out:  # every answer type is reported separately
        e["label"] = "correct" if len(out) == 1 else ("reply" if e["kind"] == "reply" else e["tool"])
    return out


def open_days(business: dict, today: date) -> list[str]:
    days = [resolve_day(today, f"+{k}") for k in range(0, 8)]
    return [str(d) for d in days
            if business["schedule"][["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()]]]


def build_case(cat: str, d: dict, business: dict, now: datetime, style: dict, text: dict):
    """Returns (messages, expect options, situation text, extra meta)."""
    today = now.date()
    reg = style["register"]
    services = {s["id"]: s for s in business["services"]}
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
    target = str(resolve_day(today, d["day"])) if "day" in d and cat != "unseen_tool" else None

    def fill(s: str, slots=None, descs=None) -> str:
        if not s:
            return s
        kw = {}
        if slots:
            t1, t2 = slots[0], slots[1] if len(slots) > 1 else slots[0]
            kw = dict(t1=fmt_time(t1, reg), t2=fmt_time(t2, reg), h1=fmt_hour(t1), h2=fmt_hour(t2))
        if descs:
            kw.update(b1=descs[0], b2=descs[1])
        return s.format(**kw)

    if "expect" in d and cat not in ("pressure",):  # a per-case override of the usual expectation
        c.user(c1)
        exp = options_from_spec(d["expect"], today, d.get("ctx"))
        sit = "Next: " + " OR ".join(e.get("tool", "reply (no tool)") for e in exp) + "."
    elif cat == "price":
        c.user(c1)
        exp = [expect_tool("search_services", nonempty=[] if d.get("generic") else ["query"])]
        sit = "Asks a price/duration. Next: search_services."
    elif cat in ("booking", "after_slots", "agree", "closed"):
        c.user(c1)
        c.tool("search_services", {"query": services[d["svc"]]["name"]})
        if cat == "booking":
            exp = [expect_tool("get_available_slots", exact={"service_id": d["svc"], "date": target})]
            sit = f"Wants {d['svc']} on {target} ('{d['day']}' from {now:%a %Y-%m-%d %H:%M}). Next: get_available_slots({d['svc']}, {target})."
        elif cat == "closed":
            exp = [expect_reply(label="explains_hours"),
                   expect_tool("get_available_slots", exact={"service_id": d["svc"]},
                               args_in={"date": open_days(business, today)}, label="checks_open_day")]
            sit = f"Asks for {d['svc']} at a closed day/time (around {target}). Next: explain hours, or check an open day."
        else:
            c.tool("get_available_slots", {"service_id": d["svc"], "date": target})
            if cat == "after_slots":
                exp = [expect_reply()]
                sit = f"Wants {d['svc']} on {target}; free: {', '.join(d['slots'])}. Next: offer only these times, do not book yet."
            else:
                c.assistant(fill(text["assistant_1"], slots=d["slots"]))
                c.user(fill(text["customer_2"], slots=d["slots"]))
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
            descs = [f"{services[b['service_id']]['short_name']} يوم {WEEKDAYS_AR[date.fromisoformat(b['date']).weekday()]}"
                     f" الساعة {fmt_time(b['time'], reg)}" for b in bookings]
            if d["step"] == 2:
                exp = [expect_reply()]
                sit = f"Wants to cancel; has 2 bookings ({bookings[0]['service_id']}, {bookings[1]['service_id']}). Next: ask which one, do not cancel yet."
            else:
                c.assistant(fill(text["assistant_1"], descs=descs))
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
               expect_tool("cancel_booking", exact={"booking_id": b["booking_id"]}, label="old_pattern"),
               expect_reply(label="confirms_first", must_mention_times=[d["new"]])]
        sit = (f"Has {b['service_id']} on {b['date']} {b['time']}; wants {new_date} {d['new']} (free). "
               "Next: reschedule_booking (a tool never seen in training), or confirm the new time first.")
    elif cat == "pressure":
        c.user(c1)
        if d.get("ctx"):
            c.tool("search_services", {"query": services[d["ctx"]]["name"]})
        exp = options_from_spec(d["expect"], today, d.get("ctx"))
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
    if BUSINESS_FILE:
        businesses = json.loads(BUSINESS_FILE.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in businesses}
    sheet = read_sheet()
    now_keys = list(NOW)
    cases, problems, warnings = [], [], []
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
            if LATIN_WORD.search(v):
                problems.append(f"{cid}: {k} looks like Arabizi (R12): {v!r}")
            if k == "assistant_1" and v:
                if style["emoji"] == "off":
                    text[k] = EMOJI.sub("", v).strip()
                if "{t" in v and TIME_WORDS.search(re.sub(r"\{[^}]*\}", "", v)):
                    warnings.append(f"{cid}: assistant_1 has its own time-of-day word next to a filled time (R4): {v!r}")
        try:
            messages, expect, situation, extra = build_case(cat, d, business, now, style, text)
        except (ValueError, KeyError, IndexError) as e:
            problems.append(f"{cid}: {e!r}")
            continue
        names = {t["function"]["name"] for t in tools} | {"reschedule_booking"}
        for e in expect:
            if e["kind"] == "tool_call" and e["tool"] not in names:
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
    return cases, problems, warnings


def cmd_sheet(force: bool, refresh: bool) -> None:
    existing = read_sheet()
    if existing and not (force or refresh):
        sys.exit(f"{SHEET} already exists (it has the reviewed text). Use --refresh to update only the "
                 "descriptive columns, or --force to overwrite everything.")
    cases, problems, _ = assemble()
    by_id = {c["id"]: c for c in cases}
    OUT.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([*INFO_FIELDS, *TEXT_FIELDS, "note"])
        for cid, split, cat, d in drafts():
            c = by_id.get(cid)
            old = existing.get(cid, {}) if refresh else {}
            texts = [old.get(k, v) if refresh and cid in existing else v for k, v in text_fields(d).items()]
            w.writerow([cid, split, cat, BUSINESS[d["b"]], "/".join(c["meta"]["style"].values()) if c else "",
                        c["situation"] if c else "", *texts, old.get("note", "")])
    print(f"wrote {SHEET} ({len(cases)} cases, {'descriptive columns refreshed' if refresh else 'new'})")
    for p in problems:
        print("PROBLEM:", p)


def cmd_build() -> None:
    cases, problems, warnings = assemble()
    for w in warnings:
        print("WARNING:", w)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        sys.exit(f"{len(problems)} problem(s): nothing written.")
    for split, path in FILES.items():
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases if c["split"] == split),
                        encoding="utf-8", newline="\n")  # LF on every OS, so the fingerprint matches git
    print(f"wrote {' and '.join(p.name for p in FILES.values())}\n")
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


# --- check ----------------------------------------------------------------------

def trigrams(text: str) -> set[str]:
    t = re.sub(r"\s+", " ", normalize_ar(EMOJI.sub("", text))).strip()
    return {t[i:i + 3] for i in range(max(len(t) - 2, 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def load_built() -> list[dict]:
    return [json.loads(l) for path in FILES.values() for l in path.read_text(encoding="utf-8").splitlines()]


def check_tool_calls(cases: list[dict], tools: list[dict]) -> list[str]:
    schema = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    schema.update({t["function"]["name"]: t["function"]["parameters"]
                   for t in json.loads((ROOT / "spec" / "tools_unseen.json").read_text(encoding="utf-8"))})
    fmt = {"date": r"\d{4}-\d{2}-\d{2}", "time": r"\d{2}:\d{2}", "after": r"\d{2}:\d{2}"}
    issues = []

    def check(cid, name, args, partial=False):
        if name not in schema:
            return issues.append(f"{cid}: unknown tool {name}")
        props, required = schema[name].get("properties", {}), schema[name].get("required", [])
        if not partial:
            issues.extend(f"{cid}: {name} missing required {r}" for r in required if r not in args)
        issues.extend(f"{cid}: {name} unknown argument {k}" for k in args if k not in props)
        issues.extend(f"{cid}: {name}.{k}={v!r} bad format" for k, v in args.items()
                      if k in fmt and isinstance(v, str) and not re.fullmatch(fmt[k], v))

    for c in cases:
        ids = set()
        for m in c["messages"]:
            for tc in m.get("tool_calls", []):
                ids.add(tc["id"])
                check(c["id"], tc["function"]["name"], tc["function"]["arguments"])
            if m["role"] == "tool":
                if m["tool_call_id"] not in ids:
                    issues.append(f"{c['id']}: tool result without a matching call")
                if "error" in json.loads(m["content"]):
                    issues.append(f"{c['id']}: error result in context")
        for e in c["expect"]["options"]:
            if e["kind"] == "tool_call":
                check(c["id"], e["tool"], {**e["args_exact"], **{k: "x" for k in e["args_nonempty"]}}, partial=True)
                if e["tool"] == "reschedule_booking" and c["tools"] != "default+unseen":
                    issues.append(f"{c['id']}: reschedule_booking expected without the unseen tool set")
    return issues


def cmd_check() -> None:
    cases = load_built()
    _, _, tools = load_spec()
    print("1. Tool calls against spec/tools.json + tools_unseen.json")
    issues = check_tool_calls(cases, tools)
    print("   " + ("pass" if not issues else "\n   ".join(issues)))

    customer = [(c["id"], c["category"], c["split"], m["content"])
                for c in cases for m in c["messages"] if m["role"] == "user"]
    grams = [(cid, cat, split, trigrams(t)) for cid, cat, split, t in customer]

    print("\n2. Near-duplicate customer lines within a category (R10, similarity >= 0.6)")
    dup = [(jaccard(a[3], b[3]), a[0], b[0]) for a, b in itertools.combinations(grams, 2)
           if a[1] == b[1] and a[0] != b[0] and jaccard(a[3], b[3]) >= 0.6]
    print("   " + ("none" if not dup else "\n   ".join(f"{s:.2f} {x} ~ {y}" for s, x, y in sorted(dup, reverse=True))))

    print("\n   Test/dev pairs across categories with similarity >= 0.6")
    cross = [(jaccard(a[3], b[3]), a[0], b[0]) for a, b in itertools.combinations(grams, 2)
             if a[2] != b[2] and a[0] != b[0] and jaccard(a[3], b[3]) >= 0.6]
    print("   " + ("none" if not cross else "\n   ".join(f"{s:.2f} {x} ~ {y}" for s, x, y in sorted(cross, reverse=True))))

    for label, path in [("bake-off messages", ROOT / "data" / "bakeoff" / "customer_messages.txt"),
                        ("probe messages (scores only, text never shown)", ROOT / "data" / "probe" / "saudi_messages.txt")]:
        print(f"\n3. Highest similarity to the {label}")
        if not path.exists():
            print("   file not present, skipped")
            continue
        ref = [trigrams(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        top = sorted(((max(jaccard(g, r) for r in ref), cid) for cid, _, _, g in grams), reverse=True)[:5]
        print("   " + ", ".join(f"{cid} {s:.2f}" for s, cid in top))

    print("\n4. Digits (R1, R2) and Arabizi (R12)")
    assistant = [(c["id"], m["content"]) for c in cases for m in c["messages"]
                 if m["role"] == "assistant" and m.get("content")]
    mixed = [cid for cid, t in assistant if HINDI_DIGITS.search(t) and ARABIC_DIGITS.search(t)]
    hindi_assistant = [cid for cid, t in assistant if HINDI_DIGITS.search(t)]
    cust_h = sum(1 for *_, t in customer if HINDI_DIGITS.search(t))
    cust_a = sum(1 for *_, t in customer if ARABIC_DIGITS.search(t))
    arabizi = [cid for cid, _, _, t in customer if LATIN_WORD.search(t)]
    print(f"   assistant turns mixing digit sets: {mixed or 'none'}; with Hindi digits: {hindi_assistant or 'none'}")
    print(f"   customer lines with Hindi digits: {cust_h}, with Arabic digits: {cust_a}")
    print(f"   Arabizi customer lines: {arabizi or 'none'}")

    if V2:
        print("\n   Highest similarity to test v1 and dev v1 customer lines (a fresh exam should not repeat them)")
        old = [(json.loads(l)["id"], trigrams(m["content"])) for f in ("test_v1.jsonl", "dev_v1.jsonl")
               for l in (OUT / f).read_text(encoding="utf-8").splitlines()
               for m in json.loads(l)["messages"] if m["role"] == "user"]
        top = sorted(((max(jaccard(g, r) for _, r in old), cid) for cid, _, _, g in grams), reverse=True)
        print("   " + ", ".join(f"{cid} {s:.2f}" for s, cid in top[:8]))

    print("\n5. Greetings against the time of day (R6)")
    bad = []
    for c in cases:
        hour = int(c["meta"]["now"][11:13])
        for m in c["messages"]:
            t = m.get("content") or ""
            if m["role"] != "tool" and (("صباح الخير" in t and hour >= 12) or ("مساء الخير" in t and hour < 12)):
                bad.append(f"{c['id']} ({c['meta']['now'][11:]})")
    print("   " + (", ".join(bad) if bad else "all consistent"))


def cmd_freeze() -> None:
    doc = DOC
    text = doc.read_text(encoding="utf-8")
    today = date.today().isoformat()
    for split, path in FILES.items():
        data = path.read_bytes()
        if b"\r" in data:
            sys.exit(f"{path.name} has Windows line endings; rebuild it before freezing.")
        digest = hashlib.sha256(data).hexdigest()
        row = f"| `data/test/{path.name}` | `{digest}` | {today} |"
        text, n = re.subn(rf"^\| `data/test/{re.escape(path.name)}` \|.*$", row, text, flags=re.M)
        if n != 1:
            sys.exit(f"could not find the {path.name} row in {doc.name}")
        print(f"{path.name}: {digest}")
    doc.write_text(text, encoding="utf-8", newline="\n")
    print(f"recorded in {doc}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "sheet":
        cmd_sheet("--force" in sys.argv, "--refresh" in sys.argv)
    elif command == "build":
        cmd_build()
    elif command == "check":
        cmd_check()
    elif command == "freeze":
        cmd_freeze()
    else:
        sys.exit(__doc__)
