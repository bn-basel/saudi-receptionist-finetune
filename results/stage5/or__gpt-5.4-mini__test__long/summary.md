# or__gpt-5.4-mini__test__long

Model `or:gpt-5.4-mini` on the **test** split (160 cases), long prompt, scorer v1.3.

**Pass rate: 158/160 = 98.8%** (95% CI 95.6%–99.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 12/12 | 100% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 13/14 | 93% |
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

- closed:checks_open_day: 5
- closed:explains_hours: 3
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8
- unseen_tool:uses_new_tool: 2

Run time: 5.7 min (2.1 s per case).

Tokens: 150,911 in, 16,422 out. Estimated cost: $0.094.
