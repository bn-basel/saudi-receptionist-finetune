# gold_v6_ckpt308__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-308` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 39/40 = 97.5%** (95% CI 87.1%–99.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 2/3 | 67% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 3/3 | 100% |
| complaint | 3/3 | 100% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 24/24 |
| Emoji switch obeyed (replies) | 16/16 |
| Replies mostly in Arabic script | 16/16 |

Answers with text (16 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 2
- unseen_tool:confirms_first: 3

Run time: 2.5 min (3.7 s per case).
