# Task specification (v1)

The contract every later stage follows: the test set (Stage 4), the benchmark harness (Stage 5), the training data (Stage 6) and training (Stage 7). Machine-readable parts live in [`spec/`](../spec/); the system prompt is built by [`scripts/prompt.py`](../scripts/prompt.py).

## 1. The job

A WhatsApp receptionist for a small Saudi business. It answers in **general Saudi dialect**, answers questions from the business info, and uses tools for everything that changes: prices, free times and bookings. It hands off to a human when it cannot help.

Out of scope for v1: payments, images and voice notes, several businesses in one chat, and regional dialects (Najdi, Hijazi, Eastern), which are planned as a later style switch.

## 2. Businesses (all fictional)

Defined in [`spec/businesses.json`](../spec/businesses.json). Map links use `example.com`.

| id | Business | City | Receptionist | Customers |
|---|---|---|---|---|
| `dental_clinic` | عيادة ابتسامة المروج لطب الأسنان | الرياض | نورة (female) | unknown |
| `salon` | صالون لمسة ورد | جدة | ريم (female) | women only |
| `car_wash` | مغسلة البريق | الدمام | فهد (male) | unknown |
| `restaurant` | مطعم سفرة الديرة | الرياض | سعود (male) | unknown |

**Gender (R11).**
- *Receptionist → customer:* masculine forms when the gender is unknown; feminine once the name or the messages show a woman; always feminine where the business's `customers` is `"women only"` (and always masculine for `"men only"`).
- *Customer → receptionist:* customers write in the masculine or the plural, unless they clearly know who is replying (they use the receptionist's name, or it is the women-only salon).

## 3. Tools

Defined in [`spec/tools.json`](../spec/tools.json) (6 tools, in every conversation):

| Tool | Arguments | Returns |
|---|---|---|
| `search_services` | `query` (empty = all) | services with `id`, name, `price_sar`, `duration_min` |
| `get_available_slots` | `service_id`, `date` (YYYY-MM-DD), `after` (HH:MM, optional) | free times on that date |
| `create_booking` | `service_id`, `date`, `time`, `customer_name` | `booking_id`, status |
| `get_my_bookings` | none (the WhatsApp number identifies the customer) | upcoming bookings |
| `cancel_booking` | `booking_id` | status |
| `handoff_to_human` | `reason` | status, expected wait |

**Unseen tool:** `reschedule_booking` ([`spec/tools_unseen.json`](../spec/tools_unseen.json)) is **never** used in training. It appears only in test cases, to measure whether the model can use a tool it was not trained on, just by reading its definition. If it can, new tools can be added later without retraining.

## 4. Expected behaviour per scenario

These are the patterns the automatic checks in Stage 5 will score.

| Scenario | Expected tool sequence | Then the reply must... |
|---|---|---|
| Price or duration question | `search_services` | quote only the returned price/duration |
| Booking | `search_services` (if the service id is unknown) → `get_available_slots` → *customer agrees* → `create_booking` | offer only returned slots; resolve "بكرة" / "الخميس بعد العشا" from `Now` and prayer times; confirm the booking details |
| Cancellation | `get_my_bookings` → *customer confirms which* → `cancel_booking` | confirm the cancellation |
| Reschedule (v1) | `get_my_bookings` → `get_available_slots` → *customer agrees* → `cancel_booking` + `create_booking` | confirm the new time |
| Question answered by the business info (hours, address, payment, policies) | none | answer from the system prompt; share the map link for location |
| Question nobody can answer (e.g. something not in the info) | `handoff_to_human` | say you'll check with the team; do not guess |
| Complaint, emergency, or "I want a person" | `handoff_to_human` | acknowledge kindly, say someone will follow up |
| Requested time is closed | `get_available_slots` for an open day | explain the hours, offer real alternatives |
| Small talk, thanks, off-topic | none | short, friendly, steer back if needed |

**Hard rules (checkable):**
1. Tool calls are well-formed: known tool name, all required arguments, dates as YYYY-MM-DD, times as HH:MM.
2. No price, duration or time appears in a reply unless it came from a tool result or the system prompt.
3. `create_booking` / `cancel_booking` only after the customer clearly agreed in their latest message, and a booked time must be one that `get_available_slots` returned.
4. Never promise to send or do something there is no tool or info for.
5. Replies are in Saudi dialect, never Modern Standard Arabic, Egyptian or Levantine.

**No Arabizi (R12).** Arabic written in Latin letters (for example `si3r`, `a7jiz`) appears nowhere: not in the test, dev or training data, and not in the model's replies. English-only customer messages and English words inside Arabic text are allowed.

## 5. Style switches

Defined in [`spec/styles.json`](../spec/styles.json). Each conversation picks one value per switch (8 combinations), and the system prompt states them:

| Switch | Values |
|---|---|
| `register` | `casual` (relaxed everyday Saudi) / `formal` (polite Saudi with honorifics, still dialect, never MSA) |
| `warmth` | `warm` (welcoming, empathetic) / `plain` (short and direct) |
| `emoji` | `on` (at most 1–2 per message) / `off` (none) |

## 6. Data format

One JSON record per conversation (JSONL files). Reference example: [`spec/example_conversation.json`](../spec/example_conversation.json).

```json
{
  "meta": {"business_id": "...", "style": {"register": "...", "warmth": "...", "emoji": "..."},
           "now": "YYYY-MM-DDTHH:MM", "prayer_times": {"Asr": "...", "Maghrib": "...", "Isha": "..."}},
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "tool_calls": [{"id": "call_1", "type": "function",
      "function": {"name": "...", "arguments": {}}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "...", "content": "{...json...}"},
    {"role": "assistant", "content": "..."}
  ]
}
```

The system prompt is **not** stored; it is rebuilt from `meta` by `build_system_prompt`, so the format can improve without rewriting data.

## 7. Token budget

Measured by [`scripts/render_example.py`](../scripts/render_example.py) with Gemma-4-12B-it's own template, on the reference booking conversation (3 tool calls, 10 messages):

| Part | Tokens |
|---|---|
| System prompt | 285 |
| 6 tool definitions | 387 |
| Conversation | 335 |
| **Total** | **1,007** of the 1,024 measured to fit in Stage 2 |

The first draft (7 detailed tools, long rules) was 1,267. Trimming saved 260 tokens. Stage 7 will try memory savings to allow ~1,280–1,536 tokens for longer chats.

**Fairness note for Stage 5:** this short prompt suits a fine-tuned model, which learns behaviour from examples. Prompt-only competitors will be tested with this prompt *and* with a longer, fully explained version, and both results are reported.

**The long prompt** is the short prompt plus `LONG_GUIDE` in [`scripts/prompt.py`](../scripts/prompt.py): §4 of this spec and its hard rules, written out as instructions (about 450 extra tokens). It was written from this spec only, before any test result was used, then run on the dev set, where it needed no changes (DeepSeek V4.1 Flash 39/40, GPT-5.4 mini 40/40, Gemini 3.8 Flash 40/40). It was frozen on 2026-09-30 before its first test run. SHA-256 of `LONG_GUIDE`: `d47989ec52544cb024f34c3b82236f1ed8fda0ff68cc688aebb7333906efea70`.
