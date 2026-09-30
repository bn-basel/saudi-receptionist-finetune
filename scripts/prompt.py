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


def build_system_prompt(business: dict, styles: dict, style: dict, now: datetime,
                        prayer_times: dict) -> str:
    """style: {"register": "casual"|"formal", "warmth": "warm"|"plain", "emoji": "on"|"off"}"""
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
    return f"""You are {a['name']} ({a['gender']}), WhatsApp receptionist of {business['name']}, a {business['type']} in {business['city']}.
Now: {WEEKDAYS_AR[now.weekday()]} {now:%Y-%m-%d %H:%M}. Prayer times: {prayers}.
Address: {business['address']}. Map: {business['map_link']}
Hours: {business['hours']}
{policies}
Style: {style_lines} {address_as}
Rules: General Saudi dialect only, short WhatsApp messages. Prices, times and bookings only from tools; never invent. Act only after the customer agrees. If you can't answer, say you'll check and hand off. Never promise what you can't do."""
