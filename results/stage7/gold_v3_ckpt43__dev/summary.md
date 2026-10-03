# gold_v3_ckpt43__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v3/checkpoint-43` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 36/40 = 90.0%** (95% CI 76.9%–96.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
| after_slots | 2/3 | 67% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 1/3 | 33% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 30/30 |
| Emoji switch obeyed (replies) | 11/11 |
| Replies mostly in Arabic script | 10/11 |

Answers with text (11 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 1

Run time: 2.8 min (4.3 s per case).
