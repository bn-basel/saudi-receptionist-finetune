# gold_v6_ckpt440_gguf-q4_k_m_ollama__v1_greeted

Model `ollama:saudi-receptionist-gemma@google/gemma-4-12B-it` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 149/160 = 93.1%** (95% CI 88.1%–96.1%)

| Category | Passed | Rate |
|---|---|---|
| price | 13/16 | 81% |
| booking | 23/24 | 96% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 11/12 | 92% |
| info | 16/16 | 100% |
| unknown | 11/12 | 92% |
| complaint | 9/10 | 90% |
| closed | 7/8 | 88% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 9/10 | 90% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 99/101 |
| Emoji switch obeyed (replies) | 58/58 |
| Replies mostly in Arabic script | 58/58 |

Answers with text (58 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 9

Run time: 2.9 min (1.1 s per case).
