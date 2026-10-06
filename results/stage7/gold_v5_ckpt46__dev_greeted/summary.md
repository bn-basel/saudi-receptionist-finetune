# gold_v5_ckpt46__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-46` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

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
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 18/18 |
| Emoji switch obeyed (replies) | 22/22 |
| Replies mostly in Arabic script | 16/22 |

Answers with text (22 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 5 |
| Times not from the calendar, customer or business hours | 5 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 4.9 min (7.4 s per case).
