# google__gemma-4-12B-it__dev

Model `hf:google/gemma-4-12B-it` on the **dev** split (40 cases), scorer v1.1.

**Pass rate: 15/40 = 37.5%** (95% CI 24.2%–53.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/4 | 0% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 0/3 | 0% |
| cancel | 1/3 | 33% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 0/3 | 0% |

| Check | Result |
|---|---|
| Tool calls well-formed | 0/0 |
| Emoji switch obeyed (replies) | 40/40 |
| Replies mostly in Arabic script | 39/40 |

Answers with text (40 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 4 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 2
- unseen_tool:confirms_first: 2

Run time: 2.8 min (4.2 s per case).
