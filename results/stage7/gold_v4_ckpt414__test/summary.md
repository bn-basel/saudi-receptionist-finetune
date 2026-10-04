# gold_v4_ckpt414__test

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 155/160 = 96.9%** (95% CI 92.9%–98.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 8/10 | 80% |
| closed | 6/8 | 75% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 103/103 |
| Emoji switch obeyed (replies) | 57/57 |
| Replies mostly in Arabic script | 56/57 |

Answers with text (57 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8
- unseen_tool:uses_new_tool: 2

Run time: 9.8 min (3.7 s per case).
