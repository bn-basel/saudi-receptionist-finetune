# allam_v1_ckpt414_gguf-q4_k_m__v1_greeted

Model `llamacpp:http://127.0.0.1:8082@humain-ai/ALLaM-7B-Instruct-preview` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 149/160 = 93.1%** (95% CI 88.1%–96.1%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 15/16 | 94% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 9/14 | 64% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 103/105 |
| Emoji switch obeyed (replies) | 55/55 |
| Replies mostly in Arabic script | 54/55 |

Answers with text (55 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 2 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- unseen_tool:confirms_first: 9

Run time: 1.4 min (0.5 s per case).
