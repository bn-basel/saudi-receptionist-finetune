# or__gpt-5.4-mini__dev__long

Model `or:gpt-5.4-mini` on the **dev** split (40 cases), long prompt, scorer v1.3.

**Pass rate: 40/40 = 100.0%** (95% CI 91.2%–100.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 27/27 |
| Emoji switch obeyed (replies) | 13/13 |
| Replies mostly in Arabic script | 13/13 |

Answers with text (13 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- closed:explains_hours: 1
- unseen_tool:confirms_first: 1
- unseen_tool:uses_new_tool: 2

Run time: 1.3 min (2.0 s per case).

Tokens: 38,153 in, 4,746 out. Estimated cost: $0.025.
