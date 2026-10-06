# gold_v6_ckpt264__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-264` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 37/40 = 92.5%** (95% CI 80.1%–97.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 2/3 | 67% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 28/28 |
| Emoji switch obeyed (replies) | 14/14 |
| Replies mostly in Arabic script | 12/14 |

Answers with text (14 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 2

Run time: 2.2 min (3.2 s per case).
