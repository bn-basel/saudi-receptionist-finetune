# Test set v2 (in progress)

Why a second test set: test v1 is partly used up. Run 4's fix was chosen by reading run 3's test failures, so v1 now
flatters the models it helped shape. v2 is a fresh final exam that no choice is ever made from; each model version
runs on it once. v1 stays frozen and becomes a practice set.

## Decisions (Basel, 2026-10-04)

- **Same size and mix as v1:** 160 test cases in the same 12 categories and counts, so scores mean the same thing.
- **4 new businesses,** in neither v1 nor the training data, so a score comes from reading the system prompt,
  not from knowing the shop.
- **Customer messages drafted by Claude** from the style kit below, then checked and fixed by Basel (no writing
  from scratch). Not by DeepSeek: it wrote the training conversations, and an exam by the same writer would partly
  test "does it sound like DeepSeek?".

## Style kit (picked by Basel)

| | Use | Don't use |
|---|---|---|
| Openings | «السلام عليكم», «مساء الخير» / «صباح الخير» | «هلا», «هلا والله» |
| "I want" | «ابي», «ودي», «بغيت», «ممكن» | |
| Typing | spelling slips («الحشوه», «بكره», «انا» without hamza), often no punctuation, both digit sets (٧ and 7) | emoji |
| Endings | none (just ends), «لو سمحت», «شكراً» / «يعطيك العافيه», urgent («ضروري») | «تكفى» |

Greetings: the customer's first message almost always opens with one; a later message in the same conversation
often skips it.

## Businesses

In [`spec/test_businesses_v2.json`](../spec/test_businesses_v2.json): a padel club (Riyadh, every day 16:00–23:30), a
nutrition clinic (Jeddah, mornings, Friday closed, Saturday short), a henna studio (Dammam, women only, Tuesday
closed) and a phone repair shop (Madinah, Friday from 16:00). None of these kinds of business is in the training data.
The week is 15–21 November 2026, with mid-November prayer times.

## Build and checks

```bash
uv run python scripts/build_testset.py sheet --v2    # review sheet: data/test/sheet_v2.csv
uv run python scripts/build_testset.py build --v2    # data/test/test_v2.jsonl
uv run python scripts/build_testset.py check --v2
uv run python scripts/run_eval.py --model oracle --split test_v2 --run oracle__test_v2   # must be 160/160
```

The builder, fake backend and scorer (v1.3) are the same as for v1, and v1 still assembles to its frozen fingerprint.
Checks on the drafts: every tool call valid; no near-duplicate lines within a category (all below 0.6); no line
closer than 0.60 to any v1 or dev line; greetings match the time of day; no Arabizi; the always-correct oracle scores
160/160.

## Freeze

Frozen after Basel's review of the sheet. Each model version is then run on it once.

| File | SHA-256 | Frozen on |
|---|---|---|
| `data/test/test_v2.jsonl` | not frozen yet | |
