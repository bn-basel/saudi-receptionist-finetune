# or__deepseek-v4.1-flash__test

Model `or:deepseek-v4.1-flash` on the **test** split (160 cases), scorer v1.2.

**Pass rate: 151/160 = 94.4%** (95% CI 89.7%–97.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 4/12 | 33% |
| complaint | 9/10 | 90% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 100/100 |
| Emoji switch obeyed (replies) | 61/61 |
| Replies mostly in Arabic script | 61/61 |

Answers with text (61 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 5
- closed:explains_hours: 3
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 1
- pressure:reply: 2
- smalltalk:reply: 1
- unseen_tool:confirms_first: 7
- unseen_tool:uses_new_tool: 3

Run time: 4.9 min (1.8 s per case).

Tokens: 157,970 in, 18,823 out. Estimated cost: $0.025.
