# or__gpt-5.4-mini__test

Model `or:gpt-5.4-mini` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 148/160 = 92.5%** (95% CI 87.3%–95.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 18/24 | 75% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 12/12 | 100% |
| info | 16/16 | 100% |
| unknown | 10/12 | 83% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 92/92 |
| Emoji switch obeyed (replies) | 68/68 |
| Replies mostly in Arabic script | 68/68 |

Answers with text (68 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- closed:explains_hours: 6
- pressure:get_my_bookings: 1
- pressure:handoff_to_human: 2
- pressure:reply: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8
- unseen_tool:uses_new_tool: 2

Run time: 5.4 min (2.0 s per case).

Tokens: 84,351 in, 20,168 out. Estimated cost: $0.077.
