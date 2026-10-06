# gold_v6_ckpt176__dev_greeted

Model `hf:google/gemma-4-12B-it@runs/gold_v6/checkpoint-176` on the **dev_greeted** split (40 cases), short prompt, scorer v1.3.

**Pass rate: 18/40 = 45.0%** (95% CI 30.7%–60.2%)

| Category | Passed | Rate |
|---|---|---|
| price | 4/4 | 100% |
| booking | 0/6 | 0% |
| after_slots | 3/3 | 100% |
| agree | 2/3 | 67% |
| cancel | 3/3 | 100% |
| info | 0/4 | 0% |
| unknown | 0/3 | 0% |
| complaint | 0/3 | 0% |
| closed | 2/2 | 100% |
| smalltalk | 1/3 | 33% |
| unseen_tool | 2/3 | 67% |
| pressure | 1/3 | 33% |

| Check | Result |
|---|---|
| Tool calls well-formed | 18/19 |
| Emoji switch obeyed (replies) | 21/21 |
| Replies mostly in Arabic script | 21/21 |

Answers with text (21 of 40) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 3 |
| Times not from the calendar, customer or business hours | 2 |
| Wrong or invented dates | 3 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:explains_hours: 2
- unseen_tool:confirms_first: 2

Run time: 2.8 min (4.2 s per case).
