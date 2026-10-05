# gold_v4_ckpt414__val_first_nogreet

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414` on the **val_first_nogreet** split (58 cases), short prompt, scorer v1.3.

**Pass rate: 56/58 = 96.6%** (95% CI 88.3%–99.0%)

| Category | Passed | Rate |
|---|---|---|
| first_handoff_to_human | 11/13 | 85% |
| first_search_services | 30/30 | 100% |
| first_reply | 10/10 | 100% |
| first_get_my_bookings | 5/5 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 47/47 |
| Emoji switch obeyed (replies) | 11/11 |
| Replies mostly in Arabic script | 11/11 |

Answers with text (11 of 58) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Run time: 3.0 min (3.1 s per case).
