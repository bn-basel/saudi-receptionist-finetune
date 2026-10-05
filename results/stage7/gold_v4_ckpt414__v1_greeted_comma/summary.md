# gold_v4_ckpt414__v1_greeted_comma

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **v1_greeted_comma** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 123/160 = 76.9%** (95% CI 69.8%–82.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 7/16 | 44% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 8/12 | 67% |
| info | 16/16 | 100% |
| unknown | 2/12 | 17% |
| complaint | 0/10 | 0% |
| closed | 6/8 | 75% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 12/14 | 86% |

| Check | Result |
|---|---|
| Tool calls well-formed | 67/67 |
| Emoji switch obeyed (replies) | 95/95 |
| Replies mostly in Arabic script | 95/95 |

Answers with text (95 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 5 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 6
- pressure:get_my_bookings: 1
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 10.0 min (3.8 s per case).
