# allam_v1_ckpt46__dev

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-46` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 31/40 = 77.5%** (95% CI 62.5%–87.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 1/3 | 33% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 0/4 | 0% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 1/3 | 33% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 36/36 |
| Emoji switch obeyed (replies) | 4/4 |
| Replies mostly in Arabic script | 4/4 |

Answers with text (4 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 2

Run time: 1.5 min (2.2 s per case).
