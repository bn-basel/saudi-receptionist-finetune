# gold_v1_ckpt150__test

Model `hf:google/gemma-4-12B-it@runs/gold_v1/checkpoint-150` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 143/160 = 89.4%** (95% CI 83.6%–93.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 23/24 | 96% |
| after_slots | 10/12 | 83% |
| agree | 12/12 | 100% |
| cancel | 10/12 | 83% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 6/10 | 60% |
| closed | 6/8 | 75% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 7/10 | 70% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 111/111 |
| Emoji switch obeyed (replies) | 49/49 |
| Replies mostly in Arabic script | 49/49 |

Answers with text (49 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:uses_new_tool: 7

Run time: 10.7 min (4.0 s per case).
