# gold_v5_ckpt506__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-506` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 33/40 = 82.5%** (95% CI 68.0%–91.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 1/6 | 17% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 20/20 |
| Emoji switch obeyed (replies) | 21/21 |
| Replies mostly in Arabic script | 13/21 |

Answers with text (21 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 6 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 3.0 min (4.5 s per case).
