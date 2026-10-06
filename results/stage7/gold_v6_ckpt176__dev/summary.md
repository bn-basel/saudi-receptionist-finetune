# gold_v6_ckpt176__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-176` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 15/40 = 37.5%** (95% CI 24.2%–53.0%)

| Category | Passed | Rate |
|---|---|---|
| price | 3/4 | 75% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 1/3 | 33% |
| cancel | 3/3 | 100% |
| info | 0/4 | 0% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 1/2 | 50% |
| smalltalk | 1/3 | 33% |
| unseen_tool | 2/3 | 67% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 20/25 |
| Emoji switch obeyed (replies) | 15/15 |
| Replies mostly in Arabic script | 15/15 |

Answers with text (15 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 1
- unseen_tool:confirms_first: 2

Run time: 2.3 min (3.5 s per case).
