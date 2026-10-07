# allam_v1_ckpt414_gguf-q8_0__v1_greeted

Model `llamacpp:http://127.0.0.1:8082@humain-ai/ALLaM-7B-Instruct-preview` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 146/160 = 91.2%** (95% CI 85.8%–94.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 14/16 | 88% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 6/8 | 75% |
| smalltalk | 9/14 | 64% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 105/106 |
| Emoji switch obeyed (replies) | 54/54 |
| Replies mostly in Arabic script | 54/54 |

Answers with text (54 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- unseen_tool:confirms_first: 9

Run time: 1.7 min (0.7 s per case).
