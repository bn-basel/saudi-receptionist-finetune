# gold_v5_ckpt548__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-548` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 35/40 = 87.5%** (95% CI 73.9%–94.5%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 3/6 | 50% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 1/2 | 50% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 20/20 |
| Emoji switch obeyed (replies) | 20/20 |
| Replies mostly in Arabic script | 14/20 |

Answers with text (20 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 3 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 3

Run time: 3.1 min (4.6 s per case).
