# allam_v1_ckpt414_gguf-q4_k_m_chat__v1_greeted

Model `llamachat:http://127.0.0.1:8090@humain-ai/ALLaM-7B-Instruct-preview` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 152/160 = 95.0%** (95% CI 90.4%–97.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 15/16 | 94% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 11/14 | 79% |
| unseen_tool | 9/10 | 90% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 103/104 |
| Emoji switch obeyed (replies) | 56/56 |
| Replies mostly in Arabic script | 56/56 |

Answers with text (56 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 1.3 min (0.5 s per case).
