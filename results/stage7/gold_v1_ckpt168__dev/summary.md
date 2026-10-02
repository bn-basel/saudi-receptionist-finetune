# gold_v1_ckpt168__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v1/checkpoint-168` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 35/40 = 87.5%** (95% CI 73.9%–94.5%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 2/3 | 67% |
| complaint | 1/3 | 33% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 26/26 |
| Emoji switch obeyed (replies) | 14/14 |
| Replies mostly in Arabic script | 13/14 |

Answers with text (14 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 2

Run time: 2.9 min (4.3 s per case).
