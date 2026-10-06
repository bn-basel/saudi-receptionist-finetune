# gold_v5_ckpt184__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-184` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 37/40 = 92.5%** (95% CI 80.1%–97.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 2/3 | 67% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 25/25 |
| Emoji switch obeyed (replies) | 15/15 |
| Replies mostly in Arabic script | 15/15 |

Answers with text (15 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 2

Run time: 2.4 min (3.6 s per case).
