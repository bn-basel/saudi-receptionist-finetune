"""Charts for the README, drawn as plain SVG from the saved result files (no plotting library).

    uv run python scripts/make_charts.py      # writes docs/charts/*.svg

Every number comes from results/*/summary.json or runs/<run>/log_history.json, so the charts can be redrawn
whenever a result changes and never drift from the files they describe.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "charts"
FONT = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"
INK, GRID, MUTED, OURS, API, OPEN = "#1f2328", "#d0d7de", "#656d76", "#1a7f37", "#8c959f", "#bf8700"
RUN_GREENS = ["#a8dbb2", "#5fb874", OURS]  # one green per fine-tuning run, darker as the data grows
RUNS = [  # fine-tuning runs: name, label, chosen checkpoint, conversations trained on
    ("gold_v1", "run 1", 150, 352),
    ("gold_v2", "run 2", 315, 874),
    ("gold_v3", "run 3", 387, 1086),
]


def summary(path: str) -> dict:
    return json.loads((ROOT / "results" / path / "summary.json").read_text(encoding="utf-8"))


def svg(width: int, height: int, body: list[str]) -> str:
    # a white background, so the chart reads the same in GitHub's light and dark themes
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            f"<rect width='100%' height='100%' fill='#ffffff'/>" + "".join(body) + "</svg>\n")


def text(x, y, s, size=13, anchor="start", color=INK, weight="normal") -> str:
    return (f"<text x='{x}' y='{y}' {FONT} font-size='{size}' text-anchor='{anchor}' fill='{color}' "
            f"font-weight='{weight}'>{s}</text>")


def test_scores() -> None:
    """Test-set score per model, short prompt and (where it was run) long prompt, with 95% intervals."""
    rows = [  # label, kind, short-prompt run, long-prompt run
        ("ALLaM-7B (HUMAIN), prompted", OPEN, "stage5/humain-ai__ALLaM-7B-Instruct-preview__test",
         "stage5/humain-ai__ALLaM-7B-Instruct-preview__test__long"),
        ("Gemma-4-12B, untuned", OPEN, "stage5/google__gemma-4-12B-it__test", "stage5/google__gemma-4-12B-it__test__long"),
        *[(f"Gemma-4-12B + QLoRA, {label} ({n} conv.)", RUN_GREENS[k - len(RUNS)],
           f"stage7/{run}_ckpt{ck}__test", None) for k, (run, label, ck, n) in enumerate(RUNS)],
        ("Gemini 3.8 Flash (API)", API, "stage5/or__gemini-3.8-flash__test", "stage5/or__gemini-3.8-flash__test__long"),
        ("GPT-5.4 mini (API)", API, "stage5/or__gpt-5.4-mini__test", "stage5/or__gpt-5.4-mini__test__long"),
        ("DeepSeek V4.1 Flash (API)", API, "stage5/or__deepseek-v4.1-flash__test", "stage5/or__deepseek-v4.1-flash__test__long"),
    ]
    left, top, bar_w, row_h, w = 300, 70, 420, 44, 810
    body = [text(20, 30, "Test set: share of 160 cases handled correctly (tool calls and facts)", 16, weight="bold"),
            text(20, 50, "Solid bar: short system prompt (the one the fine-tuned model uses). Light bar: long prompt. "
                         "Whiskers: 95% interval.", 12, color=MUTED)]
    for p in range(0, 101, 20):
        x = left + bar_w * p / 100
        body.append(f"<line x1='{x}' y1='{top - 6}' x2='{x}' y2='{top + row_h * len(rows)}' stroke='{GRID}'/>")
        body.append(text(x, top + row_h * len(rows) + 16, f"{p}%", 11, "middle", MUTED))
    for i, (label, color, short, long) in enumerate(rows):
        y = top + i * row_h
        bold = "bold" if color in RUN_GREENS else "normal"
        body.append(text(left - 10, y + 17, label, 13, "end", weight=bold))
        if long:
            ls = summary(long)
            body.append(f"<rect x='{left}' y='{y + 22}' width='{bar_w * ls['pass_rate']:.1f}' height='9' fill='{color}' "
                        f"opacity='0.35'/>")
            body.append(text(left + bar_w * ls["pass_rate"] + 6, y + 31, f"{ls['pass_rate']:.0%} long", 10, color=MUTED))
        s = summary(short)
        x_end = left + bar_w * s["pass_rate"]
        body.append(f"<rect x='{left}' y='{y + 6}' width='{x_end - left:.1f}' height='15' fill='{color}'/>")
        lo, hi = (left + bar_w * c for c in s["ci95"])
        body.append(f"<line x1='{lo:.1f}' y1='{y + 13.5}' x2='{hi:.1f}' y2='{y + 13.5}' stroke='{INK}' stroke-width='1.2'/>")
        body.append(text(left + bar_w + 8, y + 18, f"{s['pass_rate']:.1%}", 13, weight=bold))
    (OUT / "test_scores.svg").write_text(svg(w, top + row_h * len(rows) + 30, body), encoding="utf-8")


def checkpoint_curve() -> None:
    """Dev-set score after each saved checkpoint of every run, by passes over the data (the runs have different
    numbers of steps), against the untuned model and the best API model."""
    curves = []
    for k, (run, label, _, n) in enumerate(RUNS):
        log = json.loads((ROOT / "runs" / run / "log_history.json").read_text(encoding="utf-8"))
        per_epoch = max(e["step"] / e["epoch"] for e in log if e.get("epoch"))
        steps = sorted({e["step"] for e in log if "eval_loss" in e})
        points = [(s / per_epoch, summary(f"stage7/{run}_ckpt{s}__dev")["pass_rate"]) for s in steps
                  if (ROOT / "results" / "stage7" / f"{run}_ckpt{s}__dev" / "summary.json").exists()]
        curves.append((f"{label}: {n} conversations", RUN_GREENS[k - len(RUNS)], points))
    refs = [("untuned Gemma", summary("stage5/google__gemma-4-12B-it__dev")["pass_rate"], OPEN),
            ("DeepSeek V4.1 Flash (API)", summary("stage5/or__deepseek-v4.1-flash__dev")["pass_rate"], API)]
    passes = max(p for _, _, pts in curves for p, _ in pts)
    left, top, w, h, pw, ph = 70, 60, 880, 380, 560, 270
    xs = lambda x: left + pw * x / passes
    ys = lambda rate: top + ph * (1 - rate)
    body = [text(20, 28, "More data, more training: dev-set score after each checkpoint (40 cases)", 16, weight="bold"),
            text(20, 46, "QLoRA on reviewed conversations, same recipe in every run. With 40 cases, ±10 points is noise.",
                 12, color=MUTED)]
    for p in range(0, 101, 20):
        body.append(f"<line x1='{left}' y1='{ys(p / 100):.1f}' x2='{left + pw}' y2='{ys(p / 100):.1f}' stroke='{GRID}'/>")
        body.append(text(left - 8, ys(p / 100) + 4, f"{p}%", 11, "end", MUTED))
    for e in range(1, round(passes) + 1):
        x = xs(e)
        body.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{top + ph}' stroke='{GRID}' stroke-dasharray='3 3'/>")
        body.append(text(x, top + ph + 18, f"pass {e}", 11, "middle", MUTED))
    for label, rate, color in refs:
        body.append(f"<line x1='{left}' y1='{ys(rate):.1f}' x2='{left + pw}' y2='{ys(rate):.1f}' stroke='{color}' "
                    f"stroke-width='1.5' stroke-dasharray='6 4'/>")
        body.append(text(left + pw + 8, ys(rate) + 4, f"{label} {rate:.0%}", 12, color=color))
    for label, color, points in curves:
        path = " ".join(f"{'M' if i == 0 else 'L'}{xs(x):.1f},{ys(r):.1f}" for i, (x, r) in enumerate([(0, refs[0][1])] + points))
        body.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2.5'/>")
        body += [f"<circle cx='{xs(x):.1f}' cy='{ys(r):.1f}' r='4' fill='{color}'/>" for x, r in points]
    # legend under the plot, so the labels never collide with the reference lines on the right
    for k, (label, color, _) in enumerate(curves):  # one row per run
        y = top + ph + 56 + 20 * k
        body.append(f"<line x1='{left}' y1='{y}' x2='{left + 22}' y2='{y}' stroke='{color}' stroke-width='3'/>")
        body.append(text(left + 28, y + 4, f"fine-tuned Gemma, {label}", 12, color=INK, weight="bold"))
    body.append(text(left + pw / 2, top + ph + 34, "passes over the training data", 12, "middle", MUTED))
    (OUT / "checkpoint_curve.svg").write_text(svg(w, h + 30 + 20 * (len(curves) - 1), body), encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    test_scores()
    checkpoint_curve()
    print(f"wrote {', '.join(p.name for p in sorted(OUT.glob('*.svg')))} to {OUT}")
