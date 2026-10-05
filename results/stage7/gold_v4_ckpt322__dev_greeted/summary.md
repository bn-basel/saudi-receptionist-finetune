# gold_v4_ckpt322__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-322` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 27/40 = 67.5%** (95% CI 52.0%–79.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/4 | 25% |
| booking | 5/6 | 83% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 0/3 | 0% |

| Check | Result |
|---|---|
| Tool calls well-formed | 12/15 |
| Emoji switch obeyed (replies) | 25/25 |
| Replies mostly in Arabic script | 25/25 |

Answers with text (25 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 2.8 min (4.2 s per case).
