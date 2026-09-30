# humain-ai__ALLaM-7B-Instruct-preview__dev__long

Model `hf:humain-ai/ALLaM-7B-Instruct-preview` on the **dev** split (40 cases), long prompt, scorer v1.3.

**Pass rate: 13/40 = 32.5%** (95% CI 20.1%–48.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/4 | 0% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 0/3 | 0% |
| cancel | 1/3 | 33% |
| info | 3/4 | 75% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 1/2 | 50% |
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
| Invented numbers (prices, counts) | 7 |
| Times not from the calendar, customer or business hours | 4 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 3 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 2

Run time: 0.6 min (0.8 s per case).
