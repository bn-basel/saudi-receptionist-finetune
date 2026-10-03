# gold_v2_ckpt315__test

Model `hf:google/gemma-4-12B-it@runs/gold_v2/checkpoint-315` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 148/160 = 92.5%** (95% CI 87.3%–95.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 22/24 | 92% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 10/12 | 83% |
| complaint | 8/10 | 80% |
| closed | 5/8 | 62% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 101/101 |
| Emoji switch obeyed (replies) | 59/59 |
| Replies mostly in Arabic script | 58/59 |

Answers with text (59 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 5
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 10.6 min (4.0 s per case).
