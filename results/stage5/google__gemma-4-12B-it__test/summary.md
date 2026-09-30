# google__gemma-4-12B-it__test

Model `hf:google/gemma-4-12B-it` on the **test** split (160 cases), scorer v1.1.

**Pass rate: 65/160 = 40.6%** (95% CI 33.3%–48.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 2/16 | 12% |
| booking | 0/24 | 0% |
| after_slots | 10/12 | 83% |
| agree | 0/12 | 0% |
| cancel | 3/12 | 25% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 7/8 | 88% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 4/14 | 29% |

| Check | Result |
|---|---|
| Tool calls well-formed | 2/2 |
| Emoji switch obeyed (replies) | 155/155 |
| Replies mostly in Arabic script | 154/155 |

Answers with text (155 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 4 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 5 |
| Claims an action no tool performed | 13 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 7
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 9.6 min (3.6 s per case).
