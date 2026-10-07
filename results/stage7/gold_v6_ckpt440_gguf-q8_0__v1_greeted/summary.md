# gold_v6_ckpt440_gguf-q8_0__v1_greeted

Model `llamacpp:http://127.0.0.1:8082@google/gemma-4-12B-it` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 154/160 = 96.2%** (95% CI 92.1%–98.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 23/24 | 96% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 97/97 |
| Emoji switch obeyed (replies) | 63/63 |
| Replies mostly in Arabic script | 63/63 |

Answers with text (63 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 1 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 3
- closed:explains_hours: 4
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 2.4 min (0.9 s per case).
