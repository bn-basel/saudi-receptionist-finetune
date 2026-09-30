# google__gemma-4-12B-it__test__long

Model `hf:google/gemma-4-12B-it` on the **test** split (160 cases), long prompt, scorer v1.3.

**Pass rate: 71/160 = 44.4%** (95% CI 36.9%–52.1%)

| Category | Passed | Rate |
|---|---|---|
| price | 3/16 | 19% |
| booking | 0/24 | 0% |
| after_slots | 12/12 | 100% |
| agree | 0/12 | 0% |
| cancel | 4/12 | 33% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 1/10 | 10% |
| closed | 7/8 | 88% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 5/14 | 36% |

| Check | Result |
|---|---|
| Tool calls well-formed | 5/5 |
| Emoji switch obeyed (replies) | 143/143 |
| Replies mostly in Arabic script | 142/143 |

Answers with text (143 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 11 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 7
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 10.9 min (4.1 s per case).
