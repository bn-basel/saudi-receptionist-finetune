# google__gemma-4-12B-it__test_v2

Model `hf:google/gemma-4-12B-it` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 69/160 = 43.1%** (95% CI 35.7%–50.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/16 | 6% |
| booking | 0/24 | 0% |
| after_slots | 12/12 | 100% |
| agree | 0/12 | 0% |
| cancel | 4/12 | 33% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 4/14 | 29% |

| Check | Result |
|---|---|
| Tool calls well-formed | 1/1 |
| Emoji switch obeyed (replies) | 160/160 |
| Replies mostly in Arabic script | 159/160 |

Answers with text (160 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 3 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 11 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 8
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 9.1 min (3.4 s per case).
