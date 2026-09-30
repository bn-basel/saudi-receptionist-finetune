# humain-ai__ALLaM-7B-Instruct-preview__test__long

Model `hf:humain-ai/ALLaM-7B-Instruct-preview` on the **test** split (160 cases), long prompt, scorer v1.3.

**Pass rate: 67/160 = 41.9%** (95% CI 34.5%–49.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/16 | 0% |
| booking | 0/24 | 0% |
| after_slots | 10/12 | 83% |
| agree | 1/12 | 8% |
| cancel | 5/12 | 42% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 3/14 | 21% |

| Check | Result |
|---|---|
| Tool calls well-formed | 3/3 |
| Emoji switch obeyed (replies) | 160/160 |
| Replies mostly in Arabic script | 159/160 |

Answers with text (160 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 31 |
| Times not from the calendar, customer or business hours | 10 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 9 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 8
- pressure:reply: 2
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 2.3 min (0.9 s per case).
