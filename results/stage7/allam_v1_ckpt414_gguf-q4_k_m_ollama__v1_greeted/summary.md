# allam_v1_ckpt414_gguf-q4_k_m_ollama__v1_greeted

Model `ollama:allam-saudi-receptionist@humain-ai/ALLaM-7B-Instruct-preview` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 145/160 = 90.6%** (95% CI 85.1%–94.2%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 13/16 | 81% |
| unknown | 11/12 | 92% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 10/14 | 71% |
| unseen_tool | 8/10 | 80% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 106/107 |
| Emoji switch obeyed (replies) | 53/53 |
| Replies mostly in Arabic script | 53/53 |

Answers with text (53 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8

Run time: 1.7 min (0.6 s per case).
