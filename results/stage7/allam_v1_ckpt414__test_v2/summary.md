# allam_v1_ckpt414__test_v2

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-414` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 140/160 = 87.5%** (95% CI 81.5%–91.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 23/24 | 96% |
| after_slots | 10/12 | 83% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 11/16 | 69% |
| unknown | 9/12 | 75% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 10/14 | 71% |
| unseen_tool | 9/10 | 90% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 112/113 |
| Emoji switch obeyed (replies) | 47/47 |
| Replies mostly in Arabic script | 47/47 |

Answers with text (47 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:handoff_to_human: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8
- unseen_tool:uses_new_tool: 1

Run time: 5.6 min (2.1 s per case).
