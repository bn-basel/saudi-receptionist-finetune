# gold_v6_ckpt440_gguf-q4_k_m_chat__v1_greeted

Model `llamachat:http://127.0.0.1:8090@google/gemma-4-12B-it` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 148/160 = 92.5%** (95% CI 87.3%–95.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 23/24 | 96% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 11/12 | 92% |
| info | 14/16 | 88% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 101/101 |
| Emoji switch obeyed (replies) | 59/59 |
| Replies mostly in Arabic script | 59/59 |

Answers with text (59 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 2.1 min (0.8 s per case).
