# gold_v1_ckpt120__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v1/checkpoint-120` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 33/40 = 82.5%** (95% CI 68.0%–91.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 1/3 | 33% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 22/22 |
| Emoji switch obeyed (replies) | 18/18 |
| Replies mostly in Arabic script | 18/18 |

Answers with text (18 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 2

Run time: 2.4 min (3.6 s per case).
