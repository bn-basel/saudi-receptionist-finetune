# gold_v5_ckpt368__v1_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-368` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 150/160 = 93.8%** (95% CI 88.9%–96.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 21/24 | 88% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 11/12 | 92% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 6/8 | 75% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 11/14 | 79% |

| Check | Result |
|---|---|
| Tool calls well-formed | 96/97 |
| Emoji switch obeyed (replies) | 64/64 |
| Replies mostly in Arabic script | 62/64 |

Answers with text (64 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- closed:explains_hours: 4
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 9.8 min (3.7 s per case).
