"""Charts for the README, drawn as plain SVG from the saved result files (no plotting library).

    uv run python scripts/make_charts.py      # writes docs/charts/*.svg

Every number comes from results/*/summary.json or runs/<run>/log_history.json, so the charts can be redrawn
whenever a result changes and never drift from the files they describe. Each chart carries a light and a dark set
of colours (a CSS media query inside the SVG), so it follows the reader's light or dark theme.
"""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "charts"
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# colour name: (light theme, dark theme). Shapes take class f-<name> (fill) or s-<name> (stroke).
PALETTE = {
    "bg": ("#ffffff", "#0d1117"), "ink": ("#1f2328", "#e6edf3"), "muted": ("#656d76", "#8d96a0"),
    "grid": ("#eaeef2", "#21262d"), "axis": ("#afb8c1", "#484f58"), "white": ("#ffffff", "#ffffff"), "onours": ("#ffffff", "#0d1117"),
    "ours": ("#1a7f37", "#3fb950"), "api": ("#8c959f", "#6e7681"), "open": ("#bf8700", "#d29922"),
    # one green per fine-tuning run, darker (light theme) or brighter (dark theme) as the data improves
    "r1": ("#b4e2bf", "#24532f"), "r2": ("#7cc690", "#276e38"), "r3": ("#3fa45c", "#2a8a40"),
    # heatmap: every case passed, 90%+, 75%+, 50%+, some, none
    "h5": ("#1a7f37", "#238636"), "h4": ("#9bd5a9", "#1f5f30"), "h3": ("#f2d27a", "#6b5110"),
    "h2": ("#f3ac7a", "#7c3b12"), "h1": ("#f2a6a0", "#6e211d"), "h0": ("#cf222e", "#b62324"),
    # kinds of invented facts
    "numbers": ("#cf222e", "#f85149"), "times": ("#bc4c00", "#db6d28"), "dates": ("#8250df", "#a371f7"),
    "actions": ("#0969da", "#4493f8"),
    "allam": ("#0e7c86", "#2bb3c0"),  # ALLaM fine-tuned on the same data
}
RUN_COLOURS = ["r1", "r2", "r3", "ours"]
ALLAM_RUN = ("allam_v1", 414)  # HUMAIN's ALLaM-7B, fine-tuned on exactly run 4's conversations
RUNS = [  # fine-tuning runs: name, label, chosen checkpoint, conversations trained on, what changed (two lines)
    ("gold_v1", "run 1", 150, 352, ("first reviewed", "conversations")),
    ("gold_v2", "run 2", 315, 874, ("more of the", "same data")),
    ("gold_v3", "run 3", 387, 1086, ("+213 aimed at weak", "spots: two got worse")),
    ("gold_v4", "run 4", 414, 1162, ("82 bad first moves out,", "134 good ones in")),
]
BASELINES = [  # label, colour, short-prompt run (test set); the long-prompt run adds __long
    ("ALLaM-7B (HUMAIN), prompted", "open", "stage5/humain-ai__ALLaM-7B-Instruct-preview__test"),
    ("Gemma-4-12B, untuned", "open", "stage5/google__gemma-4-12B-it__test"),
    ("Gemini 3.8 Flash (API)", "api", "stage5/or__gemini-3.8-flash__test"),
    ("GPT-5.4 mini (API)", "api", "stage5/or__gpt-5.4-mini__test"),
    ("DeepSeek V4.1 Flash (API)", "api", "stage5/or__deepseek-v4.1-flash__test"),
]
CATEGORIES = [  # key in summary.json, column header (one or two lines)
    ("price", ["Prices"]), ("booking", ["Bookings"]), ("after_slots", ["Offer", "times"]),
    ("agree", ["Confirm", "booking"]), ("cancel", ["Cancel"]), ("info", ["Business", "info"]),
    ("unknown", ["Unknown", "questions"]), ("complaint", ["Complaints"]), ("closed", ["Closed", "days"]),
    ("smalltalk", ["Small", "talk"]), ("unseen_tool", ["New", "tool"]), ("pressure", ["Pressure", "tests"]),
]
INVENTED = [  # key in summary.json reply_problems, legend label, colour
    ("Invented numbers (prices, counts)", "invented price or number", "numbers"),
    ("Times not from the calendar, customer or business hours", "unchecked time", "times"),
    ("Wrong or invented dates", "wrong date", "dates"),
    ("Claims an action no tool performed", "claimed action never done", "actions"),
]


def summary(path: str) -> dict:
    return json.loads((ROOT / "results" / path / "summary.json").read_text(encoding="utf-8"))


def run_path(run: str, ckpt: int, split: str = "test") -> str:
    return f"stage7/{run}_ckpt{ckpt}__{split}"


def style() -> str:
    light = "".join(f".f-{k}{{fill:{l}}}.s-{k}{{stroke:{l}}}" for k, (l, _) in PALETTE.items())
    dark = "".join(f".f-{k}{{fill:{d}}}.s-{k}{{stroke:{d}}}" for k, (_, d) in PALETTE.items())
    return f"<style>text{{font-family:{FONT}}}{light}@media (prefers-color-scheme:dark){{{dark}}}</style>"


def save(name: str, title: str, width: float, height: float, body: list[str]) -> None:
    # a rounded card with its own background, so the chart reads well on any page colour
    (OUT / f"{name}.svg").write_text(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width:.0f}' height='{height:.0f}' "
        f"viewBox='0 0 {width:.0f} {height:.0f}' role='img'><title>{escape(title)}</title>{style()}"
        f"<rect x='0.5' y='0.5' width='{width - 1:.0f}' height='{height - 1:.0f}' rx='12' class='f-bg s-grid'/>"
        + "".join(body) + "</svg>\n", encoding="utf-8", newline="\n")


def text(x, y, s, size=13, anchor="start", colour="ink", weight="normal") -> str:
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}' class='f-{colour}' "
            f"font-weight='{weight}'>{escape(str(s))}</text>")


def rect(x, y, w, h, colour, rx=0, opacity=1.0) -> str:
    op = f" fill-opacity='{opacity}'" if opacity < 1 else ""
    return f"<rect x='{x:.1f}' y='{y:.1f}' width='{max(w, 0):.1f}' height='{h:.1f}' rx='{rx}' class='f-{colour}'{op}/>"


def line(x1, y1, x2, y2, colour, width=1.0, dash="") -> str:
    d = f" stroke-dasharray='{dash}'" if dash else ""
    return (f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' class='s-{colour}' "
            f"stroke-width='{width}'{d}/>")


def header(title: str, subtitle: str) -> list[str]:
    return [text(24, 36, title, 19, weight="bold"), text(24, 58, subtitle, 12.5, colour="muted")]


def test_scores() -> None:
    """The headline: the fine-tuned model against every baseline on the test set, best first."""
    run, _, ck, n, _ = RUNS[-1]
    rows = [("Gemma-4-12B + QLoRA (this project)", "ours", run_path(run, ck), None, f"fine-tuned on {n:,} "
             "conversations, one RTX 5080")]
    notes = {"DeepSeek V4.1 Flash (API)": "the model Mujawib runs on today", "ALLaM-7B (HUMAIN), prompted":
             "Saudi Arabia's open model", "Gemma-4-12B, untuned": "the same model before fine-tuning"}
    rows.append(("ALLaM-7B + QLoRA (this project)", "allam", run_path(*ALLAM_RUN), None,
                 "HUMAIN's model, same data, tool calling added"))
    rows += [(label, colour, path, f"{path}__long", notes.get(label, "commercial API")) for label, colour, path in BASELINES]
    rows.sort(key=lambda r: -summary(r[2])["pass_rate"])
    left, top, bar_w, row_h, w = 320, 112, 440, 58, 880
    body = header("Fine-tuned on one consumer GPU, level with the best API model",
                  "Test set: 160 Saudi-dialect receptionist cases, scored on tool calls and facts.")
    # legend: what the bars and whiskers mean
    body += [rect(24, 76, 22, 10, "ours", 3), text(52, 85, "short system prompt", 11.5, colour="muted"),
             rect(186, 79, 22, 4, "api", 2, 0.5), text(214, 85, "long, fully explained prompt", 11.5, colour="muted"),
             line(398, 81, 420, 81, "ink", 1.4), text(426, 85, "95% interval", 11.5, colour="muted")]
    for p in range(0, 101, 25):
        x = left + bar_w * p / 100
        body.append(line(x, top - 8, x, top + row_h * len(rows) - 10, "grid"))
        body.append(text(x, top + row_h * len(rows) + 6, f"{p}%", 11, "middle", "muted"))
    for i, (label, colour, short, long, note) in enumerate(rows):
        y = top + i * row_h
        weight = "bold" if colour in ("ours", "allam") else "normal"
        body += [text(left - 14, y + 13, label, 14, "end", weight=weight),
                 text(left - 14, y + 30, note, 11.5, "end", colour if colour in ("ours", "allam") else "muted")]
        s = summary(short)
        body.append(rect(left, y, bar_w, 20, "grid", 4))
        body.append(rect(left, y, bar_w * s["pass_rate"], 20, colour, 4))
        lo, hi = (left + bar_w * c for c in s["ci95"])
        body += [line(lo, y + 10, hi, y + 10, "ink", 1.4), line(lo, y + 6, lo, y + 14, "ink", 1.4),
                 line(hi, y + 6, hi, y + 14, "ink", 1.4)]
        body.append(text(left + bar_w + 14, y + 15, f"{s['pass_rate']:.1%}", 15, weight="bold",
                         colour="ours" if colour == "ours" else "ink"))
        if long:
            ls = summary(long)
            body.append(rect(left, y + 25, bar_w * ls["pass_rate"], 5, colour, 2, 0.5))
            body.append(text(left + bar_w + 14, y + 31, f"{ls['pass_rate']:.1%} long", 11, colour="muted"))
    save("test_scores", "Test-set scores of the fine-tuned model and the baselines", w, top + row_h * len(rows) + 22, body)


def runs_progress() -> None:
    """Test score of each run's chosen checkpoint, with what changed in the data, against the best API model."""
    points = [(label, n, change, summary(run_path(run, ck))) for run, label, ck, n, change in RUNS]
    deepseek = summary(BASELINES[-1][2])["pass_rate"]
    left, top, pw, ph, w, lo_y = 70, 96, 600, 250, 880, 0.80
    xs = lambda i: left + pw * (i + 0.5) / len(points)
    ys = lambda r: top + ph * (1 - (max(r, lo_y) - lo_y) / (1 - lo_y))
    body = header("Same model, same recipe: only the data changed between runs",
                  "Test score of the checkpoint chosen in each run (160 cases), with 95% intervals.")
    for p in range(80, 101, 5):
        body += [line(left, ys(p / 100), left + pw, ys(p / 100), "grid"),
                 text(left - 10, ys(p / 100) + 4, f"{p}%", 11, "end", "muted")]
    body.append(text(left - 10, top + ph + 22, "axis starts at 80%", 10.5, "start", "muted"))
    body += [line(left, ys(deepseek), left + pw, ys(deepseek), "api", 1.6, "6 4"),
             text(left + pw + 12, ys(deepseek) - 2, f"DeepSeek V4.1 Flash {deepseek:.1%}", 12, colour="api",
                  weight="bold"),
             text(left + pw + 12, ys(deepseek) + 14, "the API model Mujawib uses", 11, colour="muted")]
    for i in range(len(points) - 1):
        body.append(line(xs(i), ys(points[i][3]["pass_rate"]), xs(i + 1), ys(points[i + 1][3]["pass_rate"]),
                         "axis", 2))
    for i, (label, n, change, s) in enumerate(points):
        x, y, last = xs(i), ys(s["pass_rate"]), i == len(points) - 1
        colour = RUN_COLOURS[i - len(points)]
        lo, hi = (ys(c) for c in s["ci95"])
        body += [line(x, lo, x, hi, "ink", 1.3), line(x - 6, lo, x + 6, lo, "ink", 1.3),
                 line(x - 6, hi, x + 6, hi, "ink", 1.3),
                 f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{9 if last else 7}' class='f-{colour} s-bg' stroke-width='2.5'/>",
                 text(x + 17, y + 5, f"{s['pass_rate']:.1%}", 16 if last else 14, colour="ours" if last else "ink",
                      weight="bold")]
        base = top + ph + 46
        body += [text(x, base, label.capitalize(), 14, "middle", weight="bold"),
                 text(x, base + 18, f"{n:,} conversations", 12, "middle", "ink"),
                 text(x, base + 36, change[0], 11.5, "middle", "muted"),
                 text(x, base + 51, change[1], 11.5, "middle", "muted")]
    save("runs", "Test score per fine-tuning run", w, top + ph + 116, body)


def category_heatmap() -> None:
    """Cases passed per category, for every model, so the strengths and weak spots show at a glance."""
    groups = [
        ("Open models, prompted", [(label, path, False) for label, _, path in BASELINES[:2]]),
        ("Gemma-4-12B fine-tuned (this project)",
         [(f"{label.capitalize()}: {n:,} conv.", run_path(run, ck), k == len(RUNS) - 1)
          for k, (run, label, ck, n, _) in enumerate(RUNS)]),
        ("ALLaM-7B fine-tuned (this project)", [("Same data as run 4", run_path(*ALLAM_RUN), False)]),
        ("API models", [(label.replace(" (API)", ""), path, False) for label, _, path in BASELINES[2:]]),
    ]
    left, top, cw, ch, gap = 236, 116, 63, 30, 4
    total_x = left + len(CATEGORIES) * cw + 14
    w = total_x + 70 + 24

    def bucket(rate: float) -> str:
        return "h5" if rate == 1 else "h4" if rate >= .9 else "h3" if rate >= .75 else "h2" if rate >= .5 \
            else "h1" if rate > 0 else "h0"

    body = header("Where each model passes and fails, by kind of request",
                  "Test cases passed in each category (short system prompt for every model). "
                  "The columns follow the test-set categories.")
    for j, (_, head) in enumerate(CATEGORIES):
        x = left + j * cw + (cw - gap) / 2
        for k, part in enumerate(head):
            body.append(text(x, top - 30 + 14 * k + (7 if len(head) == 1 else 0), part, 11.5, "middle", "muted",
                             "bold"))
    body.append(text(total_x + 33, top - 23, "Total", 11.5, "middle", "muted", "bold"))
    y = top
    for g, (name, rows) in enumerate(groups):
        body.append(text(24, y + 14, name.upper(), 10.5, colour="muted", weight="bold"))
        y += 22
        for label, path, ours in rows:
            s = summary(path)
            body.append(text(left - 12, y + ch / 2 + 4, label, 13, "end", "ours" if ours else "ink",
                             "bold" if ours else "normal"))
            for j, (key, _) in enumerate(CATEGORIES):
                c = s["by_category"][key]
                b = bucket(c["passed"] / c["total"])
                body += [rect(left + j * cw, y, cw - gap, ch - gap, b, 5),
                         text(left + j * cw + (cw - gap) / 2, y + (ch - gap) / 2 + 4, f"{c['passed']}/{c['total']}",
                              11.5, "middle", "white" if b in ("h5", "h0") else "ink", "bold" if ours else "normal")]
            b = bucket(s["pass_rate"]) if s["pass_rate"] < 1 else "h5"
            body += [rect(total_x, y, 66, ch - gap, "ours" if ours else "grid", 5),
                     text(total_x + 33, y + (ch - gap) / 2 + 4, f"{s['pass_rate']:.1%}", 12, "middle",
                          "onours" if ours else "ink", "bold")]
            y += ch
        y += 10
    legend = [("h5", "all"), ("h4", "90%+"), ("h3", "75–89%"), ("h2", "50–74%"), ("h1", "under 50%"), ("h0", "none")]
    x = left
    for b, label in legend:
        body += [rect(x, y + 6, 16, 12, b, 3), text(x + 22, y + 16, label, 11.5, colour="muted")]
        x += 30 + 7.2 * len(label)
    save("categories", "Test cases passed per category, per model", w, y + 38, body)


def invented_facts() -> None:
    """Replies that invent a fact or an action, per model: the reason a receptionist model can't be untuned."""
    rows = [(BASELINES[0][0], BASELINES[0][2], "open"), (BASELINES[1][0], BASELINES[1][2], "open")]
    rows += [(f"Fine-tuned Gemma, {label}", run_path(run, ck), RUN_COLOURS[k - len(RUNS)])
             for k, (run, label, ck, _, _) in enumerate(RUNS)]
    rows.append(("Fine-tuned ALLaM (same data)", run_path(*ALLAM_RUN), "allam"))
    rows += [(label, path, "api") for label, _, path in BASELINES[2:]]
    counts = [[summary(path)["reply_problems"][key] for key, _, _ in INVENTED] for _, path, _ in rows]
    biggest = max(sum(c) for c in counts)
    left, top, bar_w, row_h, w = 300, 112, 470, 30, 880
    body = header("Made-up facts: 23 before fine-tuning, none after",
                  "Replies on the 160 test cases that invent a price, a time or a date, or claim an action "
                  "no tool performed (short prompt).")
    x = 24
    for _, label, colour in INVENTED:
        body += [rect(x, 76, 14, 12, colour, 3), text(x + 20, 86, label, 11.5, colour="muted")]
        x += 34 + 6.3 * len(label)
    for i, ((label, _, colour), c) in enumerate(zip(rows, counts)):
        y = top + i * row_h
        ours = colour == "ours"
        body.append(text(left - 14, y + 15, label, 13, "end", "ours" if ours else "ink", "bold" if ours else "normal"))
        x = left
        for n, (_, _, kind) in zip(c, INVENTED):
            seg = bar_w * n / biggest
            if n:
                body.append(rect(x, y + 2, seg - 1.5, 18, kind, 3))
                if seg > 22:
                    body.append(text(x + seg / 2, y + 15.5, n, 11, "middle", "white", "bold"))
            x += seg
        total = sum(c)
        body.append(text(x + 10, y + 16, total if total else "0: none", 13.5, colour="ink" if total else "ours",
                         weight="bold"))
        if i in (1, 6):  # separate the prompted models, the fine-tuned runs and the API models
            body.append(line(24, y + row_h - 4, w - 24, y + row_h - 4, "grid"))
    save("invented_facts", "Replies with invented facts or actions, per model", w, top + row_h * len(rows) + 14, body)


def checkpoint_curve() -> None:
    """Dev-set score after each saved checkpoint, one small panel per run (the runs have different numbers of
    steps, so the x axis is passes over the data), against the untuned model and the best API model."""
    panels = []
    for run, label, ck, n, _ in RUNS:
        log = json.loads((ROOT / "runs" / run / "log_history.json").read_text(encoding="utf-8"))
        per_epoch = max(e["step"] / e["epoch"] for e in log if e.get("epoch"))
        steps = sorted({e["step"] for e in log if "eval_loss" in e})
        points = [(s / per_epoch, summary(run_path(run, s, "dev"))["pass_rate"]) for s in steps
                  if (ROOT / "results" / run_path(run, s, "dev") / "summary.json").exists()]
        chosen = (ck / per_epoch, summary(run_path(run, ck, "dev"))["pass_rate"])
        panels.append((f"{label.capitalize()}: {n:,} conversations", points, chosen))
    untuned = summary("stage5/google__gemma-4-12B-it__dev")["pass_rate"]
    deepseek = summary("stage5/or__deepseek-v4.1-flash__dev")["pass_rate"]
    passes = max(p for _, pts, _ in panels for p, _ in pts)
    left, top, pw, ph, gap, w = 62, 124, 180, 190, 22, 880
    ys = lambda rate: top + ph * (1 - rate)
    body = header("Most of the gain comes in the first pass over the data",
                  "Dev-set score (40 cases) after each saved checkpoint. With 40 cases, a few points either way is noise.")
    body += [line(24, 81, 46, 81, "ours", 2.5), text(52, 85, "dev score", 11.5, colour="muted"),
             f"<circle cx='132' cy='81' r='6' fill='none' class='s-ink' stroke-width='1.8'/>",
             text(144, 85, "checkpoint chosen for the test", 11.5, colour="muted"),
             line(330, 81, 352, 81, "api", 1.6, "5 3"), text(358, 85, f"DeepSeek V4.1 Flash {deepseek:.0%}", 11.5, colour="muted"),
             line(530, 81, 552, 81, "open", 1.6, "5 3"), text(558, 85, f"untuned Gemma {untuned:.0%}", 11.5, colour="muted")]
    for k, (label, points, chosen) in enumerate(panels):
        x0 = left + k * (pw + gap)
        xs = lambda x: x0 + pw * x / passes
        body.append(text(x0, top - 12, label, 12.5, weight="bold"))
        for p in range(0, 101, 25):
            body.append(line(x0, ys(p / 100), x0 + pw, ys(p / 100), "grid"))
            if k == 0:
                body.append(text(x0 - 8, ys(p / 100) + 4, f"{p}%", 10.5, "end", "muted"))
        for e in range(1, round(passes) + 1):
            body.append(text(xs(e), top + ph + 16, e, 10.5, "middle", "muted"))
        body += [line(x0, ys(deepseek), x0 + pw, ys(deepseek), "api", 1.4, "5 3"),
                 line(x0, ys(untuned), x0 + pw, ys(untuned), "open", 1.4, "5 3")]
        path = " ".join(f"{'M' if i == 0 else 'L'}{xs(x):.1f},{ys(r):.1f}"
                        for i, (x, r) in enumerate([(0, untuned)] + points))
        body.append(f"<path d='{path}' fill='none' class='s-ours' stroke-width='2.2' stroke-linejoin='round'/>")
        body += [f"<circle cx='{xs(x):.1f}' cy='{ys(r):.1f}' r='3' class='f-ours'/>" for x, r in points]
        body.append(f"<circle cx='{xs(chosen[0]):.1f}' cy='{ys(chosen[1]):.1f}' r='7' fill='none' class='s-ink' "
                    f"stroke-width='1.8'/>")
    body.append(text(left + (4 * pw + 3 * gap) / 2, top + ph + 38, "passes over the training data", 12, "middle", "muted"))
    save("checkpoint_curve", "Dev-set score after each checkpoint, per run", w, top + ph + 56, body)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    test_scores()
    runs_progress()
    category_heatmap()
    invented_facts()
    checkpoint_curve()
    print(f"wrote {', '.join(p.name for p in sorted(OUT.glob('*.svg')))} to {OUT}")
