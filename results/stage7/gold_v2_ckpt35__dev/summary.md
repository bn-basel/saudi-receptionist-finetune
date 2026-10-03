# gold_v2_ckpt35

Model `hf:google/gemma-4-12B-it@runs/gold_v2/checkpoint-35` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 30/40 = 75.0%** (95% CI 59.8%–85.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/4 | 25% |
| booking | 5/6 | 83% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 1/3 | 33% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 21/21 |
| Emoji switch obeyed (replies) | 19/19 |
| Replies mostly in Arabic script | 18/19 |

Answers with text (19 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 3 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 2

Run time: 3.4 min (5.1 s per case).
