# or__deepseek-v4.1-flash__dev__long

Model `or:deepseek-v4.1-flash` on the **dev** split (40 cases), long prompt, scorer v1.3.

**Pass rate: 39/40 = 97.5%** (95% CI 87.1%–99.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
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
| Tool calls well-formed | 25/26 |
| Emoji switch obeyed (replies) | 15/15 |
| Replies mostly in Arabic script | 15/15 |

Answers with text (15 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 3

Run time: 1.4 min (2.1 s per case).

Tokens: 57,354 in, 4,763 out. Estimated cost: $0.010.
