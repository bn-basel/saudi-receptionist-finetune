# humain-ai__ALLaM-7B-Instruct-preview__test

Model `hf:humain-ai/ALLaM-7B-Instruct-preview` on the **test** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 61/160 = 38.1%** (95% CI 31.0%–45.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/16 | 0% |
| booking | 0/24 | 0% |
| after_slots | 12/12 | 100% |
| agree | 0/12 | 0% |
| cancel | 4/12 | 33% |
| info | 12/16 | 75% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 7/8 | 88% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 8/10 | 80% |
| pressure | 4/14 | 29% |

| Check | Result |
|---|---|
| Tool calls well-formed | 1/2 |
| Emoji switch obeyed (replies) | 160/160 |
| Replies mostly in Arabic script | 158/160 |

Answers with text (160 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 21 |
| Times not from the calendar, customer or business hours | 4 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 9 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 7
- pressure:reply: 3
- smalltalk:reply: 1
- unseen_tool:confirms_first: 8

Run time: 2.2 min (0.8 s per case).
