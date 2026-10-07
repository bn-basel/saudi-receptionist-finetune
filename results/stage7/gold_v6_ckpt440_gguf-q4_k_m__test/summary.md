# gold_v6_ckpt440_gguf-q4_k_m__test

Model `llamacpp:http://127.0.0.1:8082@google/gemma-4-12B-it` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 153/160 = 95.6%** (95% CI 91.2%–97.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 23/24 | 96% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 15/16 | 94% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 104/104 |
| Emoji switch obeyed (replies) | 56/56 |
| Replies mostly in Arabic script | 55/56 |

Answers with text (56 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 10

Run time: 1.8 min (0.7 s per case).
