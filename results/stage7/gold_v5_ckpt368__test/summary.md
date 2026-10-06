# gold_v5_ckpt368__test

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-368` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 142/160 = 88.8%** (95% CI 82.9%–92.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 20/24 | 83% |
| after_slots | 11/12 | 92% |
| agree | 12/12 | 100% |
| cancel | 10/12 | 83% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 4/8 | 50% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 7/10 | 70% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 104/107 |
| Emoji switch obeyed (replies) | 54/54 |
| Replies mostly in Arabic script | 52/54 |

Answers with text (54 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 3
- closed:explains_hours: 1
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 7

Run time: 9.0 min (3.4 s per case).
