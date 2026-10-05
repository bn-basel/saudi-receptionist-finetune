# gold_v4_ckpt414__val_first

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **val_first** split (58 cases), short prompt, scorer v1.3.

**Pass rate: 25/58 = 43.1%** (95% CI 31.2%–55.9%)

| Category | Passed | Rate |
|---|---|---|
| first_handoff_to_human | 0/13 | 0% |
| first_search_services | 15/30 | 50% |
| first_reply | 10/10 | 100% |
| first_get_my_bookings | 0/5 | 0% |

| Check | Result |
|---|---|
| Tool calls well-formed | 15/15 |
| Emoji switch obeyed (replies) | 45/45 |
| Replies mostly in Arabic script | 45/45 |

Answers with text (45 of 58) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 6 |
| Times not from the calendar, customer or business hours | 1 |
| Wrong or invented dates | 3 |
| Claims an action no tool performed | 0 |

Run time: 3.4 min (3.5 s per case).
