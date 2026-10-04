# allam_v1_ckpt506__dev

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-506` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 36/40 = 90.0%** (95% CI 76.9%–96.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 2/3 | 67% |
| info | 2/4 | 50% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 2/3 | 67% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 31/31 |
| Emoji switch obeyed (replies) | 9/9 |
| Replies mostly in Arabic script | 9/9 |

Answers with text (9 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 2
- unseen_tool:uses_new_tool: 1

Run time: 1.4 min (2.0 s per case).
