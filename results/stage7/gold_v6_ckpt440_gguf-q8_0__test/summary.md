# gold_v6_ckpt440_gguf-q8_0__test

Model `llamacpp:http://127.0.0.1:8082@google/gemma-4-12B-it` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 154/160 = 96.2%** (95% CI 92.1%–98.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 15/16 | 94% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 12/14 | 86% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 101/101 |
| Emoji switch obeyed (replies) | 59/59 |
| Replies mostly in Arabic script | 59/59 |

Answers with text (59 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 1 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 5
- closed:explains_hours: 2
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 2.3 min (0.9 s per case).
