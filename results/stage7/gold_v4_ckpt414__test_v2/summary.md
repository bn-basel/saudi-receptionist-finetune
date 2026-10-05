# gold_v4_ckpt414__test_v2

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 121/160 = 75.6%** (95% CI 68.4%–81.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 7/16 | 44% |
| booking | 24/24 | 100% |
| after_slots | 11/12 | 92% |
| agree | 11/12 | 92% |
| cancel | 11/12 | 92% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 1/10 | 10% |
| closed | 6/8 | 75% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 8/10 | 80% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 70/70 |
| Emoji switch obeyed (replies) | 90/90 |
| Replies mostly in Arabic script | 90/90 |

Answers with text (90 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 10 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:reply: 2
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8

Run time: 9.5 min (3.6 s per case).
