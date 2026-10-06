# gold_v5_ckpt460__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-460` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 30/40 = 75.0%** (95% CI 59.8%–85.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 0/2 | 0% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 16/16 |
| Emoji switch obeyed (replies) | 24/24 |
| Replies mostly in Arabic script | 15/24 |

Answers with text (24 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 7 |
| Times not from the calendar, customer or business hours | 4 |
| Wrong or invented dates | 3 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- unseen_tool:confirms_first: 3

Run time: 3.4 min (5.0 s per case).
