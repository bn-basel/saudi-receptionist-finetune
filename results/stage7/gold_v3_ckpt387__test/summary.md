# gold_v3_ckpt387__test

Model `hf:google/gemma-4-12B-it@runs/gold_v3/checkpoint-387` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 147/160 = 91.9%** (95% CI 86.6%–95.2%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 11/12 | 92% |
| info | 15/16 | 94% |
| unknown | 8/12 | 67% |
| complaint | 10/10 | 100% |
| closed | 4/8 | 50% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 107/107 |
| Emoji switch obeyed (replies) | 53/53 |
| Replies mostly in Arabic script | 53/53 |

Answers with text (53 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 1 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 4
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 9

Run time: 9.7 min (3.6 s per case).
