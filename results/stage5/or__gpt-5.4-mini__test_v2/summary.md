# or__gpt-5.4-mini__test_v2

Model `or:gpt-5.4-mini` on the **test_v2** split (160 cases), short prompt, scorer v1.3.

**Pass rate: 146/160 = 91.2%** (95% CI 85.8%–94.7%)

| Category | Passed | Rate |
|---|---|---|
| price | 16/16 | 100% |
| booking | 20/24 | 83% |
| after_slots | 12/12 | 100% |
| agree | 12/12 | 100% |
| cancel | 10/12 | 83% |
| info | 16/16 | 100% |
| unknown | 5/12 | 42% |
| complaint | 10/10 | 100% |
| closed | 8/8 | 100% |
| smalltalk | 14/14 | 100% |
| unseen_tool | 10/10 | 100% |
| pressure | 13/14 | 93% |

| Check | Result |
|---|---|
| Tool calls well-formed | 86/86 |
| Emoji switch obeyed (replies) | 74/74 |
| Replies mostly in Arabic script | 74/74 |

Answers with text (74 of 160) that contain (a case can have several):

| Problem | Answers |
|---|---|
| Invented numbers (prices, counts) | 2 |
| Times not from the calendar, customer or business hours | 0 |
| Wrong or invented dates | 0 |
| Claims an action no tool performed | 0 |

Accepted answer types (cases with more than one correct answer):

- closed:checks_open_day: 2
- closed:explains_hours: 6
- pressure:handoff_to_human: 2
- pressure:search_services: 1
- smalltalk:reply: 1
- unseen_tool:confirms_first: 9
- unseen_tool:uses_new_tool: 1

Run time: 4.9 min (1.8 s per case).

Tokens: 89,648 in, 21,335 out. Estimated cost: $0.082.
