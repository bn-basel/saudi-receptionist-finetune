# allam_v1_ckpt414_gguf-q4_k_m__test

Model `llamacpp:http://127.0.0.1:8082@humain-ai/ALLaM-7B-Instruct-preview` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 134/160 = 83.8%** (95% CI 77.3%–88.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 24/24 | 100% |
| after_slots | 10/12 | 83% |
| agree | 11/12 | 92% |
| cancel | 11/12 | 92% |
| info | 7/16 | 44% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 6/8 | 75% |
| smalltalk | 10/14 | 71% |
| unseen_tool | 7/10 | 70% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 126/128 |
| Emoji switch obeyed (replies) | 32/32 |
| Replies mostly in Arabic script | 31/32 |

Answers with text (32 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- smalltalk:handoff_to_human: 1
- unseen_tool:uses_new_tool: 7

Run time: 1.5 min (0.5 s per case).
