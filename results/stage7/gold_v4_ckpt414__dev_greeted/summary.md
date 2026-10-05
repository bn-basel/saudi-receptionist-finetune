# gold_v4_ckpt414__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 30/40 = 75.0%** (95% CI 59.8%–85.8%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/4 | 25% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 3/3 | 100% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 3/3 | 100% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 16/16 |
| Emoji switch obeyed (replies) | 24/24 |
| Replies mostly in Arabic script | 24/24 |

Answers with text (24 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- unseen_tool:confirms_first: 3

Run time: 2.5 min (3.8 s per case).
