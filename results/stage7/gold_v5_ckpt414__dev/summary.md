# gold_v5_ckpt414__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-414` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 27/40 = 67.5%** (95% CI 52.0%–79.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 2/3 | 67% |
| info | 3/4 | 75% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 0/2 | 0% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 17/19 |
| Emoji switch obeyed (replies) | 22/22 |
| Replies mostly in Arabic script | 12/22 |

Answers with text (22 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 8 |
| Times not from the calendar, customer or business hours | 3 |
| Wrong or invented dates | 2 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- unseen_tool:confirms_first: 2

Run time: 3.5 min (5.2 s per case).
