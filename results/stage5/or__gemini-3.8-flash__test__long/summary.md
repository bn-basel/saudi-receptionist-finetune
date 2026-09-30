# or__gemini-3.8-flash__test__long

Model `or:gemini-3.8-flash` on the **test** split (160 cases), long prompt, scorer v1.3.

**Pass rate: 146/160 = 91.2%** (95% CI 85.8%–94.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 13/16 | 81% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 3/12 | 25% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 104/104 |
| Emoji switch obeyed (replies) | 56/56 |
| Replies mostly in Arabic script | 56/56 |

Answers with text (56 of 160) that contain (a case can have several):

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
- unseen_tool:confirms_first: 9
- unseen_tool:uses_new_tool: 1

Run time: 6.9 min (2.6 s per case).

Tokens: 188,654 in, 37,962 out. Estimated cost: $0.142.
