# allam_v1_ckpt414__test

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-414` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 131/160 = 81.9%** (95% CI 75.2%–87.1%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 11/12 | 92% |
| agree | 11/12 | 92% |
| cancel | 10/12 | 83% |
| info | 6/16 | 38% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 6/8 | 75% |
| smalltalk | 10/14 | 71% |
| unseen_tool | 6/10 | 60% |
| pressure | 11/14 | 79% |

| Check | Result |
|---|---|
| Tool calls well-formed | 125/126 |
| Emoji switch obeyed (replies) | 34/34 |
| Replies mostly in Arabic script | 34/34 |

Answers with text (34 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:handoff_to_human: 2
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 4
- unseen_tool:uses_new_tool: 2

Run time: 5.7 min (2.2 s per case).
