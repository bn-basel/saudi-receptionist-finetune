# allam_v1_ckpt92__dev

Model `hf:humain-ai/ALLaM-7B-Instruct-preview@runs/allam_v1/checkpoint-92` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 29/40 = 72.5%** (95% CI 57.2%–83.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 1/3 | 33% |
| agree | 2/3 | 67% |
| cancel | 3/3 | 100% |
| info | 0/4 | 0% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 1/3 | 33% |
| unseen_tool | 1/3 | 33% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 35/35 |
| Emoji switch obeyed (replies) | 5/5 |
| Replies mostly in Arabic script | 5/5 |

Answers with text (5 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 1

Run time: 1.4 min (2.1 s per case).
