# gold_v4_ckpt138__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-138` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 27/40 = 67.5%** (95% CI 52.0%–79.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 0/4 | 0% |
| booking | 4/6 | 67% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 11/11 |
| Emoji switch obeyed (replies) | 29/29 |
| Replies mostly in Arabic script | 29/29 |

Answers with text (29 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 5 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 2
- unseen_tool:confirms_first: 3

Run time: 3.7 min (5.6 s per case).
