# gold_v5_ckpt138__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v5/checkpoint-138` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 38/40 = 95.0%** (95% CI 83.5%–98.6%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 4/6 | 67% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
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
| Tool calls well-formed | 25/26 |
| Emoji switch obeyed (replies) | 14/14 |
| Replies mostly in Arabic script | 14/14 |

Answers with text (14 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 3

Run time: 2.5 min (3.7 s per case).
