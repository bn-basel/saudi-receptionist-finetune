# gold_v5_ckpt46__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-46` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 29/40 = 72.5%** (95% CI 57.2%–83.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 19/21 |
| Emoji switch obeyed (replies) | 20/20 |
| Replies mostly in Arabic script | 13/20 |

Answers with text (20 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 7 |
| Times not from the calendar, customer or business hours | 3 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 1 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- unseen_tool:confirms_first: 2

Run time: 4.5 min (6.8 s per case).
