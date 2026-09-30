# or__gemini-3.8-flash__dev

Model `or:gemini-3.8-flash` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 37/40 = 92.5%** (95% CI 80.1%–97.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 2/3 | 67% |
| cancel | 2/3 | 67% |
| info | 4/4 | 100% |
| unknown | 2/3 | 67% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 24/24 |
| Emoji switch obeyed (replies) | 16/16 |
| Replies mostly in Arabic script | 16/16 |

Answers with text (16 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 1.7 min (2.6 s per case).

Tokens: 29,819 in, 10,815 out. Estimated cost: $0.031.
