# humain-ai__ALLaM-7B-Instruct-preview__test_v2

Model `hf:humain-ai/ALLaM-7B-Instruct-preview` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 64/160 = 40.0%** (95% CI 32.7%–47.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/16 | 0% |
| booking | 0/24 | 0% |
| after_slots | 12/12 | 100% |
| agree | 0/12 | 0% |
| cancel | 5/12 | 42% |
| info | 13/16 | 81% |
| unknown | 0/12 | 0% |
| complaint | 0/10 | 0% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 2/14 | 14% |

| Check | Result |
|---|---|
| Tool calls well-formed | 1/1 |
| Emoji switch obeyed (replies) | 160/160 |
| Replies mostly in Arabic script | 160/160 |

Answers with text (160 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 17 |
| Times not from the calendar, customer or business hours | 9 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 7 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 8
- pressure:reply: 2
- smalltalk:reply: 1
- unseen_tool:confirms_first: 10

Run time: 2.7 min (1.0 s per case).
