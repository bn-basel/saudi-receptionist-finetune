# allam_v1_ckpt414__v1_greeted

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-414` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 147/160 = 91.9%** (95% CI 86.6%–95.2%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 11/12 | 92% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 14/16 | 88% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 12/14 | 86% |
| unseen_tool | 9/10 | 90% |
| pressure | 11/14 | 79% |

| Check | Result |
|---|---|
| Tool calls well-formed | 103/104 |
| Emoji switch obeyed (replies) | 56/56 |
| Replies mostly in Arabic script | 56/56 |

Answers with text (56 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:handoff_to_human: 2
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 5.9 min (2.2 s per case).
