# gold_v6_ckpt440__test_v2

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-440` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 150/160 = 93.8%** (95% CI 88.9%–96.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 13/16 | 81% |
| booking | 23/24 | 96% |
| after_slots | 12/12 | 100% |
| agree | 11/12 | 92% |
| cancel | 12/12 | 100% |
| info | 15/16 | 94% |
| unknown | 10/12 | 83% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 98/98 |
| Emoji switch obeyed (replies) | 64/64 |
| Replies mostly in Arabic script | 63/64 |

Answers with text (64 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 5
- closed:explains_hours: 2
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 1
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 9.5 min (3.6 s per case).
