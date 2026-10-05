# or__gemini-3.8-flash__test_v2

Model `or:gemini-3.8-flash` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 141/160 = 88.1%** (95% CI 82.2%–92.3%)

| Category | Passed | Rate |
|---|---|---|
| price | 14/16 | 88% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 9/12 | 75% |
| info | 16/16 | 100% |
| unknown | 0/12 | 0% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 9/10 | 90% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 98/98 |
| Emoji switch obeyed (replies) | 62/62 |
| Replies mostly in Arabic script | 62/62 |

Answers with text (62 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 0 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 5
- closed:explains_hours: 3
- pressure:get_my_bookings: 1
- pressure:search_services: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9

Run time: 6.1 min (2.3 s per case).

Tokens: 122,782 in, 35,590 out. Estimated cost: $0.113.
