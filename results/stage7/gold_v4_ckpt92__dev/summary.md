# gold_v4_ckpt92__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-92` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 32/40 = 80.0%** (95% CI 65.2%–89.5%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 2/3 | 67% |
| agree | 1/3 | 33% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 1/3 | 33% |
| complaint | 1/3 | 33% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 20/20 |
| Emoji switch obeyed (replies) | 20/20 |
| Replies mostly in Arabic script | 20/20 |

Answers with text (20 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 1 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 2

Run time: 2.0 min (2.9 s per case).
