# gold_v5_ckpt276__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-276` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 28/40 = 70.0%** (95% CI 54.6%–81.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 1/6 | 17% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 13/18 |
| Emoji switch obeyed (replies) | 22/22 |
| Replies mostly in Arabic script | 15/22 |

Answers with text (22 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 4 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 2
- unseen_tool:confirms_first: 3

Run time: 2.4 min (3.7 s per case).
