# gold_v6_ckpt440__test

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-440` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 151/160 = 94.4%** (95% CI 89.7%–97.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 22/24 | 92% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 14/16 | 88% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 7/8 | 88% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 104/104 |
| Emoji switch obeyed (replies) | 59/59 |
| Replies mostly in Arabic script | 56/59 |

Answers with text (59 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
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

Run time: 9.6 min (3.6 s per case).
