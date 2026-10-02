# gold_v1_ckpt30__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v1/checkpoint-30` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 31/40 = 77.5%** (95% CI 62.5%–87.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 2/3 | 67% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 1/3 | 33% |
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

- closed:checks_open_day: 2
- unseen_tool:uses_new_tool: 1

Run time: 2.5 min (3.7 s per case).
