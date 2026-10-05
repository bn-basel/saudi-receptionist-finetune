# or__deepseek-v4.1-flash__test_v2

Model `or:deepseek-v4.1-flash` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 148/160 = 92.5%** (95% CI 87.3%–95.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 24/24 | 100% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 11/12 | 92% |
| info | 16/16 | 100% |
| unknown | 2/12 | 17% |
| complaint | 9/10 | 90% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 14/14 | 100% |

| Check | Result |
|---|---|
| Tool calls well-formed | 99/99 |
| Emoji switch obeyed (replies) | 68/68 |
| Replies mostly in Arabic script | 68/68 |

Answers with text (68 of 160) that contain (a case can have several):

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
- pressure:handoff_to_human: 1
- pressure:search_services: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9
- unseen_tool:uses_new_tool: 1

Run time: 5.3 min (2.0 s per case).

Tokens: 163,926 in, 20,098 out. Estimated cost: $0.028.
