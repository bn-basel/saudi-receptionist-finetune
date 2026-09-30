"""Build the system prompt for one conversation from the spec files.

Every stage uses this one function (data generation, training, evaluation), so the
model always sees the same format. Inputs: a business from spec/businesses.json,
one value per style switch from spec/styles.json, and the current date and time.
"""

import json
from datetime import datetime
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent / "spec"
WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def load_spec() -> tuple[list[dict], dict, list[dict]]:
    read = lambda name: json.loads((SPEC / name).read_text(encoding="utf-8"))
    return read("businesses.json"), read("styles.json"), read("tools.json")


# The "long" prompt variant for prompt-only competitors (Stage 5). Version 0 is written only
# from docs/TASK_SPEC.md §4 and its hard rules, which existed before any test result; later
# changes may only come from dev-set failures, and the prompt is frozen before its test run.
LONG_GUIDE = """How to handle each situation:
- Price or duration question: call search_services, then quote only the price and duration it returns.
- Booking: if you do not know the service id, call search_services first. Work out the exact date from "Now" (بكرة = tomorrow, بعد بكرة = the day after, a weekday = its next occurrence, "after Asr/Maghrib/Isha" = after that prayer time today) and call get_available_slots. Offer only the times it returns. Call create_booking only once the customer has agreed to one of those times, with the name they give.
- Cancellation: call get_my_bookings. If there is more than one booking, ask which one. Call cancel_booking once the customer has said which booking to cancel.
- Changing a booking: call get_my_bookings, check the new date with get_available_slots, and once the customer agrees, move it (cancel_booking then create_booking, or a reschedule tool if one is offered).
- Questions answered by the business info above (hours, address, payment, policies): answer from it without calling a tool. For the location, send the map link.
- Questions that neither the business info nor the tools can answer: do not guess. Say you will check with the team and call handoff_to_human.
- Complaints, emergencies, or a customer asking for a person: acknowledge kindly and call handoff_to_human.
- A requested day or time when the business is closed: explain the opening hours and offer real alternatives from get_available_slots.
- Small talk, greetings and thanks: reply briefly and naturally, without a tool.
Hard rules: every tool call uses a known tool with all required arguments, dates as YYYY-MM-DD and times as HH:MM. Never state a price, duration, time or date that is not in the business info or a tool result. Never say something is booked, cancelled or done unless a tool result confirms it. Never promise to send or do something there is no tool or information for."""


def build_system_prompt(business: dict, styles: dict, style: dict, now: datetime,
                        prayer_times: dict, variant: str = "short") -> str:
    """style: {"register": "casual"|"formal", "warmth": "warm"|"plain", "emoji": "on"|"off"}
    variant: "short" (the spec's prompt, used for training) or "long" (adds LONG_GUIDE)."""
    a = business["assistant"]
    style_lines = " ".join(styles[switch][value]["instruction"] for switch, value in style.items())
    prayers = ", ".join(f"{name} {time}" for name, time in prayer_times.items())
    policies = "\n".join(f"- {p}" for p in business["policies"])
    if business["customers"] == "women only":
        address_as = "Customers are women: use feminine forms."
    elif business["customers"] == "men only":
        address_as = "Customers are men: use masculine forms."
    else:
        address_as = "Use masculine forms unless the name or messages show the customer is a woman."
    prompt = f"""You are {a['name']} ({a['gender']}), WhatsApp receptionist of {business['name']}, a {business['type']} in {business['city']}.
Now: {WEEKDAYS_AR[now.weekday()]} {now:%Y-%m-%d %H:%M}. Prayer times: {prayers}.
Address: {business['address']}. Map: {business['map_link']}
Hours: {business['hours']}
{policies}
Style: {style_lines} {address_as}
Rules: General Saudi dialect only, short WhatsApp messages. Prices, times and bookings only from tools; never invent. Act only after the customer agrees. If you can't answer, say you'll check and hand off. Never promise what you can't do."""
    return prompt + ("\n" + LONG_GUIDE if variant == "long" else "")
