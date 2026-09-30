# or__deepseek-v4.1-flash__test__long

Model `or:deepseek-v4.1-flash` on the **test** split (160 cases), long prompt, scorer v1.3.

**Pass rate: 157/160 = 98.1%** (95% CI 94.6%–99.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 10/12 | 83% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 106/106 |
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

- closed:checks_open_day: 8
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:handoff_to_human: 1
- unseen_tool:confirms_first: 8
- unseen_tool:uses_new_tool: 2

Run time: 4.7 min (1.8 s per case).

Tokens: 227,250 in, 18,089 out. Estimated cost: $0.031.
