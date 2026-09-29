# Test set design (v1)

The exam behind every claim in the README. It is written **before** any training data, **frozen** with a SHA-256 fingerprint once finished, and **never** used to tune prompts or training. Tuning uses the separate dev set.

## 1. Sizes

| Split | Cases | Used for |
|---|---|---|
| `test` | 160 | final scores only, run once per model version |
| `dev` | 40 | tuning prompts for the competitors, sanity checks during development |

Both splits follow the same category mix. In the test split the 8 style combinations get 19–22 cases each, and the 4 businesses 32–48 each (the clinic has the most, because its opening hours create the most date and closed-time cases). At 160 cases a measured accuracy of around 80% carries roughly ±6 percentage points of 95% uncertainty.

## 2. Step-level cases

Each case is **a conversation up to a certain point, plus the one correct next step.** Earlier turns (including tool results) are fixed, so a mistake at one step cannot spoil the next, and every step of a flow is measured on its own. Tool results in the context come from a deterministic fake backend built from [`spec/`](../spec/).

## 3. Categories

| # | Category | test | dev | Expected next step |
|---|---|---|---|---|
| 1 | Price or duration question | 16 | 4 | `search_services`, then quote only the returned price |
| 2 | Booking request with a date or time phrase | 24 | 6 | the right tool with the date resolved from `Now` and prayer times |
| 3 | After slots are returned | 12 | 3 | offer only the returned slots; no booking yet |
| 4 | Customer agrees | 12 | 3 | `create_booking` with exactly the agreed arguments |
| 5 | Cancellation flow | 12 | 3 | `get_my_bookings`, then confirm, then `cancel_booking` |
| 6 | Info in the system prompt (hours, location, payment, policies) | 16 | 4 | answer from the prompt, no tool; map link for location |
| 7 | Unknown info | 12 | 3 | say you'll check + `handoff_to_human` |
| 8 | Complaint, emergency, "I want a person" | 10 | 3 | empathy + `handoff_to_human` |
| 9 | Closed day or time requested | 8 | 2 | explain hours, offer real alternatives |
| 10 | Small talk, thanks, off-topic, general chat | 14 | 3 | short friendly reply, no tool |
| 11 | Unseen tool `reschedule_booking` | 10 | 3 | use it correctly from its definition alone |
| 12 | Pressure tests (rough price, "book now, confirm later", "ignore your rules", English-only, Arabizi) | 14 | 3 | hold the rules |
| | **Total** | **160** | **40** | |

About 40 free-text test cases are flagged for the **blind dialect review** by a native speaker against the competitors.

## 4. Case format

One JSON object per line in `data/test/test_v1.jsonl` and `data/test/dev_v1.jsonl`:

```json
{
  "id": "T-001",
  "split": "test",
  "category": "price",
  "meta": {"business_id": "...", "style": {...}, "now": "...", "prayer_times": {...}},
  "tools": "default",
  "messages": ["... context up to the decision point, same format as docs/TASK_SPEC.md ..."],
  "expect": {"options": [
    {"label": "correct", "kind": "tool_call", "tool": "search_services",
     "args_exact": {}, "args_nonempty": ["query"], "args_in": {}}
  ]},
  "dialect_review": false,
  "provenance": "synthetic drafts, reviewed and edited by a native speaker"
}
```

`tools` is `"default"` (the 6 tools) or `"default+unseen"` (adds `reschedule_booking`, category 11 only). Cases also carry `situation` (the meaning in English) and, where needed, `meta.slot_overrides` (pinned free slots) and `meta.customer_bookings` (existing bookings) for the fake backend.

`expect.options` lists every acceptable next step; the first is the primary answer. Most cases have one option. Closed-time cases accept "explain the hours" or "check an open day"; unseen-tool cases label `reschedule_booking` as `uses_new_tool` and `cancel_booking` as `old_pattern`, reported separately. Each option's `kind` is one of:
- `tool_call`: the next assistant message must call `tool`, with `args_exact` matching exactly (ids, dates, times, names after Arabic normalisation), `args_nonempty` present and non-empty (free text such as `query` or `reason`), and `args_in` within a list of allowed values.
- `reply`: the next assistant message must be text with no tool call. Checks: `no_invented_numbers` (every price or time in the reply appears in the system prompt or an earlier tool result), optional `must_include_any` (e.g. the map link) and `must_not_include` (e.g. system-prompt text).

## 5. Automatic checks

| Check | Applies to |
|---|---|
| Valid tool call: known name, required arguments, date/time formats | every `tool_call` case |
| Right tool and right arguments | every `tool_call` case |
| No tool when none is expected | every `reply` case |
| No invented numbers | `reply` cases with that flag |
| Emoji switch obeyed (none when `emoji: off`) | every `reply` case |
| Saudi dialect quality | human blind A/B on the flagged subset |

Built by [`scripts/build_testset.py`](../scripts/build_testset.py) from the drafts in [`scripts/testset_drafts.py`](../scripts/testset_drafts.py) and the reviewed sheet `data/test/sheet_v1.csv`; tool results come from the fake backend [`scripts/backend.py`](../scripts/backend.py).

## 6. Authoring and provenance

Customer messages are **synthetic drafts, reviewed and edited by a native speaker**, who rewrites any line that does not sound like a real customer. Drafts deliberately include real WhatsApp habits: missing hamzas, typos, no punctuation, `ابي / ودي / بغيت`, English words and Arabizi.

Safeguards:
- No test or dev case is ever used for training, and the training data will come from a different generator than the test drafts, so the test cannot resemble the training set through a shared writer.
- Nothing from Mujawib (prompts, cases, outputs) is used in the test or dev sets.
- A leakage check (n-gram overlap) between the test set and the training data runs in Stage 6.
- Limitation, to be stated in the README: one drafting source and one human editor, so the phrasing is less varied than real customers.

## 7. Freeze

When the test set is complete and validated, its SHA-256 fingerprint is recorded here and in the README. Any later change is visible as a new fingerprint and must be versioned (`test_v2`), never edited silently.

| File | SHA-256 | Frozen on |
|---|---|---|
| `data/test/test_v1.jsonl` | _not frozen yet_ | |
| `data/test/dev_v1.jsonl` | _not frozen yet_ | |
