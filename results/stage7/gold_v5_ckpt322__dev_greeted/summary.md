# gold_v5_ckpt322__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-322` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 32/40 = 80.0%** (95% CI 65.2%–89.5%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 19/21 |
| Emoji switch obeyed (replies) | 19/19 |
| Replies mostly in Arabic script | 15/19 |

Answers with text (19 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 2 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 2.6 min (3.9 s per case).
