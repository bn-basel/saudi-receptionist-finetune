"""Fake backend: answers tool calls deterministically from spec/businesses.json.

Used to build the context of test cases now, and to run tool calls during evaluation
and data generation later. The same inputs always give the same outputs, so every
result is reproducible. Nothing here talks to a real system.

A case can pin exact free slots per date in meta["slot_overrides"], and give the
customer's existing bookings in meta["customer_bookings"].
"""

import hashlib
import re
from datetime import date, timedelta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
LAST_START = 23 * 60 + 30  # slots stay on the same calendar date


def normalize_ar(text: str) -> str:
    text = re.sub("[إأآا]", "ا", text).replace("ة", "ه").replace("ى", "ي")
    text = re.sub(r"[ً-ْـ]", "", text)  # diacritics and tatweel
    return " ".join(w[2:] if w.startswith("ال") and len(w) > 4 else w for w in text.split())


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class Backend:
    def __init__(self, business: dict, meta: dict):
        self.b = business
        self.services = {s["id"]: s for s in business["services"]}
        self.overrides = meta.get("slot_overrides", {})
        self.bookings = {x["booking_id"]: dict(x) for x in meta.get("customer_bookings", [])}

    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if fn is None or name.startswith("_") or name == "call":
            return {"error": f"unknown tool: {name}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": f"bad arguments: {e}"}

    # --- tools -----------------------------------------------------------------

    def search_services(self, query: str = "") -> dict:
        words = [w for w in normalize_ar(query).split() if len(w) >= 3]
        hits = [s for s in self.services.values()
                if not words or any(w in normalize_ar(s["name"]) for w in words)]
        return {"services": [{k: s[k] for k in ("id", "name", "price_sar", "duration_min")} for s in hits]}

    def get_available_slots(self, service_id: str, date: str, after: str | None = None) -> dict:
        if service_id not in self.services:
            return {"error": f"unknown service_id: {service_id}"}
        slots = self._slots(service_id, date)
        if slots is None:
            return {"error": "date must be YYYY-MM-DD"}
        if after:
            slots = [t for t in slots if to_min(t) >= to_min(after)]
        result = {"date": date, "slots": slots}
        if not slots and self._hours(date) is None:
            result["note"] = "closed"
        return result

    def create_booking(self, service_id: str, date: str, time: str, customer_name: str) -> dict:
        if time not in (self._slots(service_id, date) or []):
            return {"error": "slot not available"}
        booking_id = "B-" + str(int(hashlib.sha256(f"{service_id}{date}{time}".encode()).hexdigest(), 16) % 9000 + 1000)
        self.bookings[booking_id] = {"booking_id": booking_id, "service_id": service_id,
                                     "date": date, "time": time, "customer_name": customer_name}
        return {"booking_id": booking_id, "status": "confirmed"}

    def get_my_bookings(self) -> dict:
        return {"bookings": [{"booking_id": x["booking_id"], "service": self.services[x["service_id"]]["name"],
                              "service_id": x["service_id"], "date": x["date"], "time": x["time"]}
                             for x in self.bookings.values()]}

    def cancel_booking(self, booking_id: str) -> dict:
        if booking_id not in self.bookings:
            return {"error": f"unknown booking_id: {booking_id}"}
        del self.bookings[booking_id]
        return {"booking_id": booking_id, "status": "cancelled"}

    def reschedule_booking(self, booking_id: str, date: str, time: str) -> dict:
        if booking_id not in self.bookings:
            return {"error": f"unknown booking_id: {booking_id}"}
        if time not in (self._slots(self.bookings[booking_id]["service_id"], date) or []):
            return {"error": "slot not available"}
        self.bookings[booking_id].update(date=date, time=time)
        return {"booking_id": booking_id, "status": "rescheduled", "date": date, "time": time}

    def handoff_to_human(self, reason: str) -> dict:
        return {"status": "queued", "expected_wait_min": 10}

    # --- helpers ---------------------------------------------------------------

    def _hours(self, day: str) -> tuple[int, int] | None:
        spec = self.b["schedule"][DAYS[date.fromisoformat(day).weekday()]]
        if spec is None:
            return None
        start, end = spec.split("-")
        return to_min(start), to_min(end)

    def _slots(self, service_id: str, day: str) -> list[str] | None:
        try:
            date.fromisoformat(day)
        except ValueError:
            return None
        if day in self.overrides:
            return list(self.overrides[day])
        hours = self._hours(day)
        if hours is None:
            return []
        duration = self.services[service_id]["duration_min"]
        starts = range(hours[0], min(hours[1] - duration, LAST_START) + 1, 30)
        # A deterministic "busy calendar": keep about a third of the starts, at most 6.
        free = [t for t in starts
                if int(hashlib.sha256(f"{self.b['id']}{service_id}{day}{t}".encode()).hexdigest(), 16) % 3 == 0]
        return [to_hhmm(t) for t in free[:6]]


def resolve_day(now: date, spec: str) -> date:
    """'today', '+1', '+2', or a weekday ('sun'...'sat') meaning its next occurrence after today."""
    if spec == "today":
        return now
    if spec.startswith("+"):
        return now + timedelta(days=int(spec[1:]))
    target = [d.lower() for d in DAYS].index(spec)
    return now + timedelta(days=(target - now.weekday() - 1) % 7 + 1)
