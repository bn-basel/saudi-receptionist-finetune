# gold_v1_ckpt45__dev

Model `hf:google/gemma-4-12B-it@runs/gold_v1/checkpoint-45` on the **dev** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 27/40 = 67.5%** (95% CI 52.0%–79.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 5/6 | 83% |
| after_slots | 0/3 | 0% |
| agree | 2/3 | 67% |
| cancel | 2/3 | 67% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 2/3 | 67% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 0/3 | 0% |
| pressure | 3/3 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 27/27 |
| Emoji switch obeyed (replies) | 14/14 |
| Replies mostly in Arabic script | 14/14 |

Answers with text (14 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2

Run time: 2.1 min (3.2 s per case).
