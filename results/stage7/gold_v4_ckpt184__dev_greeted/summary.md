# gold_v4_ckpt184__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-184` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 29/40 = 72.5%** (95% CI 57.2%–83.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/4 | 0% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 15/15 |
| Emoji switch obeyed (replies) | 25/25 |
| Replies mostly in Arabic script | 25/25 |

Answers with text (25 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 2 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 3

Run time: 3.5 min (5.2 s per case).
