# gold_v5_ckpt276__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-276` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 23/40 = 57.5%** (95% CI 42.2%–71.5%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 3/4 | 75% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 0/2 | 0% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 11/18 |
| Emoji switch obeyed (replies) | 22/22 |
| Replies mostly in Arabic script | 12/22 |

Answers with text (22 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 8 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- unseen_tool:confirms_first: 2

Run time: 3.6 min (5.4 s per case).
