# gold_v5_ckpt460__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-460` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 30/40 = 75.0%** (95% CI 59.8%–85.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 1/6 | 17% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 2/3 | 67% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 17/18 |
| Emoji switch obeyed (replies) | 24/24 |
| Replies mostly in Arabic script | 13/24 |

Answers with text (24 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 8 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 4.0 min (6.1 s per case).
