# oracle__v1_greeted

Model `oracle` on the **v1_greeted** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 160/160 = 100.0%** (95% CI 97.7%–100.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 102/102 |
| Emoji switch obeyed (replies) | 58/58 |
| Replies mostly in Arabic script | 58/58 |

Answers with text (58 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 8
- pressure:get_my_bookings: 1
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:uses_new_tool: 10

Run time: 0.0 min (0.0 s per case).
