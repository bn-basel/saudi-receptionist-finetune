# or__gemini-3.8-flash__test

Model `or:gemini-3.8-flash` on the **test** split (160 cases), scorer v1.2.

**Pass rate: 140/160 = 87.5%** (95% CI 81.5%–91.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 15/16 | 94% |
| booking | 23/24 | 96% |
| after_slots | 11/12 | 92% |
| agree | 12/12 | 100% |
| cancel | 9/12 | 75% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 13/14 | 93% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 99/99 |
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
- pressure:reply: 1
- unseen_tool:confirms_first: 9
- unseen_tool:uses_new_tool: 1

Run time: 6.9 min (2.6 s per case).

Tokens: 117,294 in, 32,491 out. Estimated cost: $0.105.
