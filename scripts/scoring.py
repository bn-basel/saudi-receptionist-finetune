"""Stage 5: score one model step against a test case (no model code here).

A "step" is what the model produced at the decision point:
    {"text": str | None, "tool_calls": [{"name": str, "arguments": dict}, ...]}

A case passes if the step matches any of its expected options (docs/TEST_SET.md §4).
Style checks (emoji switch, Arabic script) are reported separately and do not
change pass/fail. Scorer version and changes: docs/TEST_SET.md §5.
"""

import json
import math
import re

from backend import normalize_ar

SCORER_VERSION = "1.2"

ARABIC = f"{chr(0x0600)}-{chr(0x06FF)}"
EMOJI = re.compile(f"[{chr(0x1F300)}-{chr(0x1FAFF)}{chr(0x2600)}-{chr(0x27BF)}]")
TO_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Digit boundaries use lookarounds, not \b: an Arabic letter glued to a number ("و8:30",
# "بـ250") is a word character too, so \b would not match there.
DATE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
TIME = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
KEYCAP = re.compile(f"\\d{chr(0xFE0F)}?{chr(0x20E3)}")  # emoji list numbers like 1️⃣
DURATION = re.compile(r'"duration_min":\s*(\d+)')
NUMBER = re.compile(r"\d+(?:[,.]\d+)?")
LIST_MARKER = re.compile(r"^\s*[-•*]?\s*\d{1,2}[.)-](?=\s)", re.M)  # "1. " "2) " at the start of a line only
URL = re.compile(r"https?://\S+")
FORMATS = {"date": re.compile(r"\d{4}-\d{2}-\d{2}"), "time": re.compile(r"\d{2}:\d{2}"),
           "after": re.compile(r"\d{2}:\d{2}")}

# A number is used *as a time* when it sits next to one of these words.
TIME_AFTER = r"(?:ونص|وربع|الا ربع|إلا ربع)?\s*(?:الصبح|الصباح|صباحا|صباحاً|الظهر|ظهرا|ظهراً|العصر|عصرا|عصراً" \
             r"|المسا|المساء|مساء|مساءً|مساءا|الليل|بالليل|ليلا|ليلاً|الفجر|am|pm|AM|PM)"
TIME_MENTION = re.compile(rf"(?:الساعة|الساعه)\s*(\d{{1,2}})|(?<!\d)(\d{{1,2}})\s*{TIME_AFTER}")
MONTHS = {m: i for i, names in enumerate([
    ["يناير"], ["فبراير"], ["مارس"], ["أبريل", "ابريل"], ["مايو"], ["يونيو"], ["يوليو"],
    ["أغسطس", "اغسطس"], ["سبتمبر"], ["أكتوبر", "اكتوبر"], ["نوفمبر"], ["ديسمبر"]], 1) for m in names}
DATE_MENTION = re.compile(r"(?<!\d)(\d{1,2})\s*(" + "|".join(MONTHS) + r")|(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
# A reply that says an action is done ("تم الحجز", "ألغيت لك") when no tool did it.
DONE_CLAIM = re.compile(r"(?:تم|تمت)\s+(?:ال)?(?:حجز|إلغاء|الغاء|تأكيد|تثبيت|تعديل|نقل|تغيير)"
                        r"|(?:حجزت|ألغيت|الغيت|كنسلت|ثبتت|نقلت|غيرت)\s+(?:لك|لكم|موعدك|حجزك|الموعد|الحجز)"
                        r"|انحجز|انلغى|اتلغى")
DONE_STATUS = ("confirmed", "cancelled", "rescheduled")
PRAYER_LINE = re.compile(r"Prayer times:[^\n]*")


def clean(text: str) -> str:
    """Digits in one set, links and list markers removed."""
    text = KEYCAP.sub(" ", (text or "").translate(TO_ARABIC_DIGITS))
    return LIST_MARKER.sub(" ", URL.sub(" ", text))


def with_clock_aliases(hours: set[int]) -> set[int]:
    return hours | {h % 12 or 12 for h in hours if 0 <= h <= 24} | {h + 12 for h in hours if 1 <= h <= 11}


def numbers_in(text: str, clock_aliases: bool = False) -> set[int]:
    """Every number written in the text. A date gives year, month and day; a time gives hour
    and minute. With clock_aliases, each number *used as a time* also counts in its other form
    (19 <-> 7): right for what the model MAY say, not for what it did say. A price like
    "20 ريال" gets no alias."""
    original, text = text, clean(text)
    found: set[int] = set()
    for y, mo, d in DATE.findall(text):
        found |= {int(y), int(mo), int(d)}
    text = DATE.sub(" ", text)
    for h, m in TIME.findall(text):
        found |= {int(h)} | ({int(m)} if int(m) else set())
    text = TIME.sub(" ", text)
    found |= {int(float(n.replace(",", ""))) for n in NUMBER.findall(text)}
    return found | with_clock_aliases(times_in(original)) if clock_aliases else found


def times_in(text: str) -> set[int]:
    """Hours the text uses as times: 19:30, الساعة 7, 7 المسا, 8 ونص الليل."""
    text = clean(text)
    hours = {int(h) for h, _ in TIME.findall(text)}
    for a, b in TIME_MENTION.findall(TIME.sub(" ", text)):
        hours.add(int(a or b))
    return hours


def dates_in(text: str) -> list[tuple[int, int | None]]:
    """(day, month) for dates written as '8 أكتوبر' or '8/10'."""
    out = []
    for d, month_name, d2, m2 in DATE_MENTION.findall(clean(text)):
        if month_name:
            out.append((int(d), MONTHS[month_name]))
        elif 1 <= int(m2) <= 12:
            out.append((int(d2), int(m2)))
    return out


class Context:
    """What a reply may legitimately draw on at the decision point."""

    def __init__(self, system_prompt: str, messages: list[dict]):
        customer = [m["content"] for m in messages if m["role"] == "user"]
        tool_text = [m["content"] for m in messages if m["role"] == "tool"]
        tool_text += [json.dumps(tc["function"]["arguments"], ensure_ascii=False)
                      for m in messages for tc in m.get("tool_calls", [])]
        everything = [system_prompt] + customer + tool_text
        # Prayer times may be repeated as written, but never lend a clock alias (Maghrib 17:26
        # must not make "5 ساعات" look grounded).
        prayers = " ".join(PRAYER_LINE.findall(system_prompt))
        aliasable = [PRAYER_LINE.sub(" ", system_prompt)] + customer + tool_text
        self.numbers = set().union(*(numbers_in(p, clock_aliases=True) for p in aliasable)) | numbers_in(prayers)
        # A duration may be given in hours: 240 minutes -> "4 ساعات", 150 -> "ساعتين ونص" (2).
        for t in tool_text:
            for minutes in map(int, DURATION.findall(t)):
                self.numbers |= {minutes // 60, -(-minutes // 60)} - {0}
        # Times may come from tools, the customer, or the business hours and clock in the
        # prompt, but not from prayer times (Isha 19:11 must not make "7 المسا" look real).
        time_sources = tool_text + [PRAYER_LINE.sub(" ", system_prompt)]
        self.hours = with_clock_aliases(set().union(*(numbers_in(p) & set(range(25)) for p in time_sources)))
        self.hours |= set().union(*(numbers_in(c, clock_aliases=True) for c in customer)) if customer else set()
        self.dates = {(int(d), int(mo)) for p in everything for _, mo, d in DATE.findall(clean(p))}
        self.action_done = any(f'"status": "{s}"' in t for t in tool_text for s in DONE_STATUS)


def norm_value(key: str, value) -> str:
    v = str(value).strip().translate(TO_ARABIC_DIGITS)
    if key in ("time", "after") and re.fullmatch(r"\d{1,2}:\d{2}", v):
        return v.zfill(5)
    if key == "customer_name":
        return normalize_ar(v).replace(" ", "")
    return v


def validity(call: dict, schemas: dict) -> list[str]:
    """Problems with a tool call against the tool definitions offered in this case."""
    name, args = call.get("name"), call.get("arguments")
    if name not in schemas:
        return [f"unknown tool {name!r}"]
    if not isinstance(args, dict):
        return ["arguments are not an object"]
    params = schemas[name]
    issues = [f"missing required argument {r!r}" for r in params.get("required", []) if r not in args]
    issues += [f"unknown argument {k!r}" for k in args if k not in params.get("properties", {})]
    issues += [f"{k}={v!r} has the wrong format" for k, v in args.items()
               if k in FORMATS and not FORMATS[k].fullmatch(str(v))]
    return issues


def reply_problems(text: str, ctx: Context) -> list[str]:
    """Invented numbers, times, dates or completed actions in a reply."""
    reasons = []
    invented = sorted(numbers_in(text) - ctx.numbers)
    if invented:
        reasons.append(f"invented numbers {invented}")
    off_times = sorted(h for h in times_in(text) if h not in ctx.hours)
    if off_times:
        reasons.append(f"times {off_times} come from no tool, customer or business hours")
    days = {d for d, _ in ctx.dates}
    wrong = [(d, m) for d, m in dates_in(text) if (d, m) not in ctx.dates and not (m is None and d in days)]
    if wrong:
        reasons.append(f"dates {wrong} match no real date in the conversation")
    if not ctx.action_done and DONE_CLAIM.search(text):
        reasons.append(f"claims a completed action ({DONE_CLAIM.search(text).group(0)!r}) that no tool performed")
    return reasons


def match_option(option: dict, step: dict, ctx: Context, schemas: dict) -> list[str]:
    """Empty list = the step satisfies this option; otherwise the reasons it does not."""
    calls = step.get("tool_calls") or []
    text = step.get("text") or ""
    if option["kind"] == "tool_call":
        if not calls:
            return ["expected a tool call, got a reply"]
        call = calls[0]
        if call.get("name") != option["tool"]:
            return [f"expected {option['tool']}, got {call.get('name')}"]
        reasons = validity(call, schemas)
        args = call.get("arguments") or {}
        for k, v in option["args_exact"].items():
            if norm_value(k, args.get(k, "")) != norm_value(k, v):
                reasons.append(f"{k}: expected {v!r}, got {args.get(k)!r}")
        for k in option["args_nonempty"]:
            if not str(args.get(k, "")).strip():
                reasons.append(f"{k} is empty")
        for k, values in option["args_in"].items():
            if norm_value(k, args.get(k, "")) not in {norm_value(k, v) for v in values}:
                reasons.append(f"{k}={args.get(k)!r} is not one of the allowed values")
        return reasons

    reasons = []
    if calls:
        reasons.append(f"expected a reply, got a call to {calls[0].get('name')}")
    if not text.strip():
        reasons.append("empty reply")
    if option.get("no_invented_numbers"):
        reasons += reply_problems(text, ctx)
    said = numbers_in(text)
    if option.get("no_times") and said:
        reasons.append(f"gave numbers {sorted(said)} where no time may be given")
    for t in option.get("must_mention_times", []):
        h = int(t.split(":")[0])
        if not ({h, h % 12 or 12} & said):
            reasons.append(f"does not name the time {t}")
    if option.get("must_include_any") and not any(s in text for s in option["must_include_any"]):
        reasons.append(f"missing one of {option['must_include_any']}")
    for s in option.get("must_not_include", []):
        if s in text:
            reasons.append(f"contains {s!r}")
    return reasons


def score_case(case: dict, step: dict, system_prompt: str, schemas: dict) -> dict:
    ctx = Context(system_prompt, case["messages"])
    text = step.get("text") or ""
    # Checked on every answer with text, whatever was expected: a model that says
    # "تم حجز موعدك" instead of calling create_booking fails either way, but it should
    # also count as a hallucinated action.
    extra = {**style_checks(case, step), "text_problems": reply_problems(text, ctx) if text.strip() else []}
    attempts = []
    for option in case["expect"]["options"]:
        reasons = match_option(option, step, ctx, schemas)
        if not reasons:
            return {"passed": True, "label": option["label"], "reasons": [], **extra}
        attempts.append(f"[{option['label']}] " + "; ".join(reasons))
    return {"passed": False, "label": None, "reasons": attempts, **extra}


def style_checks(case: dict, step: dict) -> dict:
    text = step.get("text") or ""
    letters = re.findall(f"[A-Za-z{ARABIC}]", URL.sub("", text))  # links don't count
    arabic = sum(1 for ch in letters if chr(0x0600) <= ch <= chr(0x06FF))
    out = {"tool_call_valid": None, "emoji_ok": None, "mostly_arabic": None}
    if step.get("tool_calls"):
        out["tool_call_valid"] = True  # filled in by the caller with the real schema check
    if text.strip():
        out["emoji_ok"] = not (case["meta"]["style"]["emoji"] == "off" and EMOJI.search(text))
        out["mostly_arabic"] = (arabic / len(letters) >= 0.7) if letters else True
    return out


def wilson(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a pass rate; honest even for small counts."""
    if total == 0:
        return 0.0, 0.0
    p = passed / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - half), min(1.0, centre + half)
