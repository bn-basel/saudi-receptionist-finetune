# gold_v4_ckpt414_nothought__val_first

Model `hf:google/gemma-4-12B-it@runs/gold_v4/checkpoint-414~nothought` on the **val_first** split (58 cases), short prompt, scorer v1.3.

**Pass rate: 57/58 = 98.3%** (95% CI 90.9%–99.7%)

| Category | Passed | Rate |
|---|---|---|
| first_handoff_to_human | 12/13 | 92% |
| first_search_services | 30/30 | 100% |
| first_reply | 10/10 | 100% |
| first_get_my_bookings | 5/5 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 48/48 |
| Emoji switch obeyed (replies) | 10/10 |
| Replies mostly in Arabic script | 10/10 |

Answers with text (10 of 58) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Run time: 2.6 min (2.7 s per case).
