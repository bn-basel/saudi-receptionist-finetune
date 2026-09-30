"""Stage 5: run a model over the test or dev set and score it.

Writes results/stage5/<run>/predictions.jsonl (one line per case, written as it goes, so an
interrupted run resumes where it stopped) and summary.md / summary.json.

Run:
  uv run python scripts/run_eval.py --model hf:google/gemma-4-12B-it --split dev
  uv run python scripts/run_eval.py --model oracle --split test          # harness self-check
  uv run python scripts/run_eval.py --rescore results/stage5/<run>       # re-score saved outputs
"""

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from prompt import build_system_prompt, load_spec
from scoring import SCORER_VERSION, score_case, validity, wilson

ROOT = Path(__file__).resolve().parent.parent
SPLITS = {"test": ROOT / "data" / "test" / "test_v1.jsonl", "dev": ROOT / "data" / "test" / "dev_v1.jsonl"}


def load_cases(split: str) -> list[dict]:
    return [json.loads(l) for l in SPLITS[split].read_text(encoding="utf-8").splitlines()]


def case_inputs(case: dict, businesses: dict, styles: dict, tools: list, unseen: list) -> tuple[str, list]:
    meta = case["meta"]
    system = build_system_prompt(businesses[meta["business_id"]], styles, meta["style"],
                                 datetime.fromisoformat(meta["now"]), meta["prayer_times"])
    return system, tools + (unseen if case["tools"] == "default+unseen" else [])


def score_all(cases: list[dict], preds: dict, spec) -> list[dict]:
    businesses, styles, tools, unseen = spec
    rows = []
    for case in cases:
        if case["id"] not in preds:
            continue
        step = preds[case["id"]]["step"]
        system, case_tools = case_inputs(case, businesses, styles, tools, unseen)
        schemas = {t["function"]["name"]: t["function"]["parameters"] for t in case_tools}
        s = score_case(case, step, system, schemas)
        if step.get("tool_calls"):
            s["tool_call_valid"] = all(not validity(c, schemas) for c in step["tool_calls"])
        rows.append({"id": case["id"], "category": case["category"], "split": case["split"],
                     "business": case["meta"]["business_id"], "style": "/".join(case["meta"]["style"].values()),
                     **s})
    return rows


def summarize(rows: list[dict], run: str, model: str, split: str, seconds: float | None) -> tuple[str, dict]:
    n, k = len(rows), sum(r["passed"] for r in rows)
    lo, hi = wilson(k, n)
    by_cat = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["category"]][0] += r["passed"]
        by_cat[r["category"]][1] += 1
    labels = Counter(f"{r['category']}:{r['label']}" for r in rows if r["passed"] and r["label"] != "correct")
    rate = lambda key: (sum(1 for r in rows if r[key]), sum(1 for r in rows if r[key] is not None))
    problem_kinds = {"invented numbers": "Invented numbers (prices, counts)",
                     "come from no tool": "Times not from the calendar, customer or business hours",
                     "match no real date": "Wrong or invented dates",
                     "claims a completed action": "Claims an action no tool performed"}
    problems = {label: sum(1 for r in rows if any(key in x for x in r.get("text_problems", [])))
                for key, label in problem_kinds.items()}
    with_text = sum(1 for r in rows if r["emoji_ok"] is not None)
    data = {"run": run, "model": model, "split": split, "scorer": SCORER_VERSION, "cases": n, "passed": k,
            "pass_rate": k / n if n else 0, "ci95": [lo, hi],
            "by_category": {c: {"passed": a, "total": b} for c, (a, b) in by_cat.items()},
            "answer_types": dict(labels), "tool_call_valid": rate("tool_call_valid"),
            "emoji_ok": rate("emoji_ok"), "mostly_arabic": rate("mostly_arabic"),
            "reply_problems": problems, "seconds": seconds}
    lines = [f"# {run}", "", f"Model `{model}` on the **{split}** split ({n} cases), scorer v{SCORER_VERSION}.", "",
             f"**Pass rate: {k}/{n} = {data['pass_rate']:.1%}** (95% CI {lo:.1%}–{hi:.1%})", "",
             "| Category | Passed | Rate |", "|---|---|---|"]
    lines += [f"| {c} | {a}/{b} | {a / b:.0%} |" for c, (a, b) in by_cat.items()]
    lines += ["", "| Check | Result |", "|---|---|"]
    for key, label in [("tool_call_valid", "Tool calls well-formed"), ("emoji_ok", "Emoji switch obeyed (replies)"),
                       ("mostly_arabic", "Replies mostly in Arabic script")]:
        a, b = data[key]
        lines.append(f"| {label} | {a}/{b} |")
    lines += ["", f"Answers with text ({with_text} of {n}) that contain (a case can have several):", "",
              "| Problem | Answers |", "|---|---|"]
    lines += [f"| {label} | {n_} |" for label, n_ in problems.items()]
    if labels:
        lines += ["", "Accepted answer types (cases with more than one correct answer):", ""]
        lines += [f"- {k_}: {v}" for k_, v in sorted(labels.items())]
    if seconds:
        lines += ["", f"Run time: {seconds / 60:.1f} min ({seconds / max(n, 1):.1f} s per case)."]
    return "\n".join(lines) + "\n", data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--run", help="run name (default: model + split)")
    ap.add_argument("--limit", type=int, help="only the first N cases (for a quick try)")
    ap.add_argument("--rescore", help="re-score an existing run folder without calling the model")
    args = ap.parse_args()

    businesses, styles, tools = load_spec()
    unseen = json.loads((ROOT / "spec" / "tools_unseen.json").read_text(encoding="utf-8"))
    spec = ({b["id"]: b for b in businesses}, styles, tools, unseen)

    if args.rescore:
        out = Path(args.rescore)
        meta = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        args.model, args.split, run = meta["model"], meta["split"], meta["run"]
        seconds = meta.get("seconds")
    else:
        run = args.run or f"{args.model.replace('hf:', '').replace('/', '__')}__{args.split}"
        out = ROOT / "results" / "stage5" / run
        out.mkdir(parents=True, exist_ok=True)
        seconds = None

    cases = load_cases(args.split)[: args.limit] if args.limit else load_cases(args.split)
    pred_path = out / "predictions.jsonl"
    preds = {}
    if pred_path.exists():
        preds = {p["id"]: p for p in map(json.loads, pred_path.read_text(encoding="utf-8").splitlines())}

    if not args.rescore:
        todo = [c for c in cases if c["id"] not in preds]
        print(f"{run}: {len(cases)} cases, {len(preds)} already done, {len(todo)} to run")
        if todo:
            from models import load_model
            model = load_model(args.model)
            start = time.time()
            with pred_path.open("a", encoding="utf-8", newline="\n") as f:
                for i, case in enumerate(todo, 1):
                    system, case_tools = case_inputs(case, *spec)
                    t = time.time()
                    step = model.step(case, system, case_tools)
                    rec = {"id": case["id"], "step": step, "seconds": round(time.time() - t, 2)}
                    preds[case["id"]] = rec
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"[{i}/{len(todo)}] {case['id']} ({rec['seconds']}s)")
            seconds = time.time() - start

    rows = score_all(cases, preds, spec)
    (out / "scores.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                      encoding="utf-8", newline="\n")
    text, data = summarize(rows, run, args.model, args.split, seconds)
    (out / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    (out / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print("\n" + text)


if __name__ == "__main__":
    main()
