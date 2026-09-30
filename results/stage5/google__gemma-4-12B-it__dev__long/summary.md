# google__gemma-4-12B-it__dev__long

Model `hf:google/gemma-4-12B-it` on the **dev** split (40 cases), long prompt, scorer v1.3.

**Pass rate: 16/40 = 40.0%** (95% CI 26.3%–55.4%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/4 | 25% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 0/3 | 0% |
| cancel | 1/3 | 33% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 0/3 | 0% |

| Check | Result |
|---|---|
| Tool calls well-formed | 1/1 |
| Emoji switch obeyed (replies) | 36/36 |
| Replies mostly in Arabic script | 36/36 |

Answers with text (36 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 5 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 2.6 min (3.8 s per case).
