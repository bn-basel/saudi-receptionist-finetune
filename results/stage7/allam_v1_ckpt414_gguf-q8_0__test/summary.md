# allam_v1_ckpt414_gguf-q8_0__test

Model `llamacpp:http://127.0.0.1:8082@humain-ai/ALLaM-7B-Instruct-preview` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 129/160 = 80.6%** (95% CI 73.8%–86.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 10/12 | 83% |
| agree | 11/12 | 92% |
| cancel | 11/12 | 92% |
| info | 8/16 | 50% |
| unknown | 10/12 | 83% |
| complaint | 10/10 | 100% |
| closed | 6/8 | 75% |
| smalltalk | 9/14 | 64% |
| unseen_tool | 3/10 | 30% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 126/127 |
| Emoji switch obeyed (replies) | 33/33 |
| Replies mostly in Arabic script | 33/33 |

Answers with text (33 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 1
- unseen_tool:uses_new_tool: 2

Run time: 1.8 min (0.7 s per case).
