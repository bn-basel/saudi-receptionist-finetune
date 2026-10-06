# gold_v5_ckpt322__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-322` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 28/40 = 70.0%** (95% CI 54.6%–81.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 2/3 | 67% |
| closed | 1/2 | 50% |
| smalltalk | 2/3 | 67% |
| unseen_tool | 2/3 | 67% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 19/22 |
| Emoji switch obeyed (replies) | 18/18 |
| Replies mostly in Arabic script | 13/18 |

Answers with text (18 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 6 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 2

Run time: 3.4 min (5.1 s per case).
