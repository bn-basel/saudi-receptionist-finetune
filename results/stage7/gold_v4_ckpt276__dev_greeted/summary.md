# gold_v4_ckpt276__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-276` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 28/40 = 70.0%** (95% CI 54.6%–81.9%)

| Category | Passed | Rate |
|---|---|---|
| price | 1/4 | 25% |
| booking | 6/6 | 100% |
| after_slots | 3/3 | 100% |
| agree | 3/3 | 100% |
| cancel | 2/3 | 67% |
| info | 4/4 | 100% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 3/3 | 100% |
| unseen_tool | 2/3 | 67% |
| pressure | 2/3 | 67% |

| Check | Result |
|---|---|
| Tool calls well-formed | 14/14 |
| Emoji switch obeyed (replies) | 27/27 |
| Replies mostly in Arabic script | 27/27 |

Answers with text (27 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 1 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 1 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 1
- closed:explains_hours: 1
- unseen_tool:confirms_first: 2

Run time: 2.5 min (3.8 s per case).
