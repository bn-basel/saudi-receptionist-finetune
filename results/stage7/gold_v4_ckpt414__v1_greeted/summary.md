# gold_v4_ckpt414__v1_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 117/160 = 73.1%** (95% CI 65.8%–79.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 7/16 | 44% |
| booking | 24/24 | 100% |
| after_slots | 11/12 | 92% |
| agree | 12/12 | 100% |
| cancel | 7/12 | 58% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 6/8 | 75% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 11/14 | 79% |

| Check | Result |
|---|---|
| Tool calls well-formed | 63/63 |
| Emoji switch obeyed (replies) | 98/98 |
| Replies mostly in Arabic script | 98/98 |

Answers with text (98 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 3 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 11.2 min (4.2 s per case).
