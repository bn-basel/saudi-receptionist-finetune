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
import json
import os
import random
import re
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
TEACHER = "deepseek-v4.1-flash"
MAX_CUSTOMER_TURNS = 4
MAX_TOOL_STEPS = 5
TOKEN_LIMIT = 1280  # hard cap; Stage 2 measured 1,024 as safe, Stage 7 may extend it
DAYS_EN = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Writing rules for the teacher: the native-speaker decisions from the Stage 4 review.
TEACHER_RULES = """Writing rules for every reply (decided by a native Saudi reviewer):
- Write like a real Saudi receptionist texting on WhatsApp: short, natural spoken Saudi. Never Modern Standard Arabic, Egyptian or Levantine words (no ماذا، لماذا، أريد، الآن، سوف، يرجى، حسنًا).
- Numbers and times use the digits 0-9. Never mix ٠-٩ and 0-9 in one message.
- Formal style says times as "8 المساء" or "10 الصباح". Casual style says "10 الصبح", "1 الظهر", "4 العصر", "7 المسا", "9 الليل".
- Never repeat a time-of-day word next to a time ("بكرة الصبح 8 الصبح" is wrong).
- Use short spoken service names ("الكشف", "التنظيف", "الجلسة العائلية"), not the full catalogue name.
- Formal: greet with "حياك الله" or an honorific. Warm: add a kind phrase. Plain: nothing extra. Emoji off: no emoji at all.
- Masculine forms unless you know the customer is a woman; always feminine at a women-only business.
- Greetings must fit the time of day. Never write Arabic in Latin letters.
Examples of the natural Saudi register to follow (real Saudi service dialogues):
"""
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


def voho_examples(k: int = 8) -> list[str]:
    """Short, natural staff replies from VohoAI/voho-saudi-dialogues (Apache-2.0), with no
    digits and no claimed actions, used only as style samples in the teacher's prompt."""
    from scoring import DONE_CLAIM
    path = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/datasets--VohoAI--voho-saudi-dialogues/snapshots/*/*.jsonl"))[0]
    replies = [m["content"] for l in open(path, encoding="utf-8") for m in json.loads(l)["messages"]
               if m["role"] == "assistant"]
    good = [r for r in replies if 4 <= len(r.split()) <= 14 and not re.search(r"[0-9٠-٩]", r)
            and not DONE_CLAIM.search(r) and sum(w in r for w in SAUDI_WORDS) >= 2
            and not any(w in r for w in MSA_WORDS)]
    return random.Random(7).sample(good, k)


def sample_scenario(rng: random.Random, businesses: list[dict]) -> dict:
    business = rng.choice(businesses)
    kind = rng.choices(["price", "booking", "cancel", "reschedule", "info", "unknown", "complaint", "closed",
                        "smalltalk", "english", "pressure"], weights=[12, 30, 10, 8, 10, 7, 6, 5, 6, 3, 3])[0]
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
    elif kind in ("booking", "english"):
        d = rng.choice(open_days)
        pref = rng.choice(["", " after Asr", " in the evening", " in the morning", " around a specific hour you choose"])
        name = rng.choice(CUSTOMER_NAMES[gender])
        goal = (f"Book '{s}' {day_phrase(d)}{pref}. Pick one of the times the receptionist offers (or ask for another "
                f"day if none suit). Give your name '{name}' when asked. End once the booking is confirmed.")
        if kind == "english":
            goal += " Write every message in English."
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
        "kind": kind, "goal": goal, "business": business,
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
    if c["typos"]:
        style.append("type casually: no hamza, small typos, little punctuation")
    if c["english_words"]:
        style.append("mix in an English word or two the way Saudis do")
    if c["emoji"]:
        style.append("sometimes add an emoji")
    system = (f"You play a customer texting '{b['name']}' ({b['type']}, {b['city']}) on WhatsApp. "
              f"Your goal: {sc['goal']} {'; '.join(style)}. Write ONLY your next WhatsApp message, usually 2-15 words, "
              "in natural Saudi dialect (never Modern Standard Arabic, never Arabic in Latin letters unless told to write "
              "English). React to what the receptionist said. If your goal is done or cannot be done, reply exactly [END].")
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


def generate_one(idx: int, sc: dict, teacher: OpenRouterModel, spec: tuple, rules: str) -> tuple[dict | None, list[str], float]:
    _, styles, tools = spec
    b, meta = sc["business"], sc["meta"]
    now = datetime.fromisoformat(meta["now"])
    order = [tools[i] for i in meta["tools_order"]]
    system_long = build_system_prompt(b, styles, meta["style"], now, meta["prayer_times"], "long") + "\n\n" + rules
    backend = Backend(b, meta)
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
    rec = {"id": f"gen-{idx:05d}", "source": f"generated ({COMPETITORS[TEACHER]['model']})", "scenario": sc["kind"],
           "goal": sc["goal"], "meta": meta_out, "messages": messages}
    return rec, [], spent


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
            g = trigrams(m["content"])
            best = max((jaccard(g, t) for t in test_grams), default=0)
            if best >= 0.6:
                problems.append(f"customer line too close to a test/dev line ({best:.2f})")
    # Flags go to the native-speaker review instead of rejecting: word lists are too crude
    # to judge dialect on their own.
    replies = " ".join(m["content"] for m in rec["messages"] if m["role"] == "assistant" and m.get("content"))
    rec["flags"] = []
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
    spec_list = (businesses, styles, tools)
    spec_by_id = ({b["id"]: b for b in businesses}, styles, tools)
    rules = TEACHER_RULES + "\n".join(f"- {r}" for r in voho_examples())
    tok = AutoTokenizer.from_pretrained("google/gemma-4-12B-it")
    test_grams = [trigrams(m["content"]) for f in ("test_v1.jsonl", "dev_v1.jsonl")
                  for l in (ROOT / "data" / "test" / f).read_text(encoding="utf-8").splitlines()
                  for m in json.loads(l)["messages"] if m["role"] == "user"]
    teacher = OpenRouterModel(TEACHER)
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
        rec, problems, spent = generate_one(idx, sc, teacher, spec_list, rules)
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

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, enumerate(scenarios)))
    print(f"\nkept {state['kept']}, rejected {state['rejected']}, cost ${state['spent']:.3f} this run")


def cmd_recheck(args) -> None:
    """Re-apply the current checks to every generated conversation of a run (kept or rejected)."""
    from transformers import AutoTokenizer

    businesses = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
    _, styles, tools = load_spec()
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
    print(f"kept {len(kept)}, rejected {len(rejected)}")
    for r in rejected:
        print(f"  {r['id']} {r['scenario']:10s} {r['problems'][0][:90]}")


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


def cmd_sheet(args) -> None:
    path = OUT_DIR / f"{args.name}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    out = OUT_DIR / f"{args.name}.review.csv"
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
    s = sub.add_parser("sheet")
    s.add_argument("name")
    rc = sub.add_parser("recheck")
    rc.add_argument("name")
    a = ap.parse_args()
    {"generate": cmd_generate, "sheet": cmd_sheet, "recheck": cmd_recheck}[a.cmd](a)
