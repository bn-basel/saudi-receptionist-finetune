---
license: apache-2.0
base_model: google/gemma-4-12B-it
language:
- ar
library_name: peft
pipeline_tag: text-generation
tags:
- arabic
- saudi-dialect
- tool-calling
- function-calling
- customer-service
- qlora
- gguf
---

# Gemma-4-12B Saudi receptionist (tool calling)

Google's [Gemma-4-12B-it](https://huggingface.co/google/gemma-4-12B-it), fine-tuned with QLoRA on one RTX 5080 to work
as a **Saudi-dialect WhatsApp receptionist that calls tools**: it looks up prices, checks free times, books, cancels
and hands the conversation to a person.

**On a fresh 160-case test it scores 93.8%, level with DeepSeek V4.1 Flash (92.5%) and GPT-5.4 mini (91.2%), running
on one consumer GPU at no cost per reply.**

Part of the open project [saudi-dialect](https://github.com/<github-user>/saudi-dialect): code, training data, both
test sets and every raw result are public there.

## Results

Scored automatically on 160 test cases (one decision each: the right tool with the right arguments, or the right
reply), short system prompt, scorer v1.3. Test v2 uses four businesses that appear in neither training nor test v1.

| Model | Test v2 (95% CI) | Made-up facts |
|---|---|---|
| **This model** | **93.8% (89–97%)** | **3** |
| DeepSeek V4.1 Flash (API) | 92.5% (87–96%) | 0 |
| GPT-5.4 mini (API) | 91.2% (86–95%) | 2 |
| Gemini 3.8 Flash (API) | 88.1% (82–92%) | 0 |
| ALLaM-7B, fine-tuned the same way ([sister model](https://huggingface.co/<hf-user>/allam-7b-saudi-receptionist)) | 87.5% (81–92%) | 2 |
| Gemma-4-12B-it, untuned | 43.1% (36–51%) | 16 |

Against DeepSeek: 10 cases won, 8 lost (paired McNemar p = 0.81); against GPT-5.4 mini p = 0.50. All 98 of its tool
calls on test v2 were well formed. By kind of request: bookings 23/24, cancellations 12/12, complaints 10/10,
pressure tests 14/14, unknown questions handed to a person 10/12 (DeepSeek 2/12); weakest on price questions (13/16).

Note: this is the second Gemma run on test v2. The fix behind this version (below) was diagnosed on practice sets
without reading test v2's answers, but the search began because of the first run's result.

**GGUF builds, re-tested** on the practice copy of test v1 (160 cases, as written and with a greeting added), with
the same prompts as the original: GGUF_RESULTS

## Use it with thinking switched off, exactly as trained

Gemma 4 has a thinking mode. This model was trained and tested **with thinking off**, which makes Gemma's chat
template put an empty thinking block (`<|channel>thought` … `<channel|>`) at the start of each new answer. Use the same
setting: `enable_thinking=False` in transformers, or `"chat_template_kwargs": {"enable_thinking": false}` with
llama-server. This matters: an earlier version trained without that block in its training text lost about 20 points
on greeted messages, because at test time it made its first move from a position it had never been trained at.
This version is trained on exactly the prompts it is tested with (each training position checked character by
character).

## Run it

**llama.cpp / LM Studio:** download `saudi-receptionist-gemma-4-12b-Q4_K_M.gguf` (6.9 GB) or `Q8_0` (11.8 GB).

```bash
llama-server -m saudi-receptionist-gemma-4-12b-Q4_K_M.gguf -ngl 99 -c 4096 --jinja
```

```python
# OpenAI-style request to llama-server; tool calls come back in the standard tool_calls field
{"messages": [...], "tools": [...], "chat_template_kwargs": {"enable_thinking": false}}
```

**Transformers + PEFT** (the adapter in this repository):

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

tok = AutoTokenizer.from_pretrained("google/gemma-4-12B-it")
model = AutoModelForCausalLM.from_pretrained("google/gemma-4-12B-it", device_map="auto")
model = PeftModel.from_pretrained(model, "<hf-user>/saudi-receptionist-gemma-4-12b")
prompt = tok.apply_chat_template([{"role": "system", "content": system_prompt}] + conversation, tools=tools,
                                 add_generation_prompt=True, enable_thinking=False, tokenize=False)
```

**The system prompt** it was trained with (one per business; the project's
[`scripts/prompt.py`](https://github.com/<github-user>/saudi-dialect/blob/main/scripts/prompt.py) builds it):

```text
You are نورة (female), WhatsApp receptionist of عيادة ابتسامة المروج لطب الأسنان, a dental clinic in الرياض.
Now: الاثنين 2026-10-05 18:40. Prayer times: Asr 15:12, Maghrib 17:41, Isha 19:11.
Address: ... Map: ...
Hours: Sun-Thu 16:00-23:00; Fri-Sat closed
- cancel or reschedule free up to 6 hours before
- payment: cash, mada, Apple Pay
Style: Relaxed everyday Saudi ... No emojis at all. Use masculine forms unless ...
Rules: General Saudi dialect only, short WhatsApp messages. Prices, times and bookings only from tools; never invent. ...
```

Tools: `search_services`, `get_available_slots`, `create_booking`, `get_my_bookings`, `cancel_booking`,
`handoff_to_human` ([schemas](https://github.com/<github-user>/saudi-dialect/blob/main/spec/tools.json)), passed in
Gemma's own tool format. On a tool it never saw in training (`reschedule_booking`) it passed 9 of 10 cases.

## Training

- **Data:** 1,153 receptionist conversations at 40 fictional Saudi businesses (1,095 for training, 58 held back).
  They were drafted on DeepSeek V4.1 Flash by the project's own generation pipeline, under 51 rules written and
  refined through review, then filtered by automatic checks and reviewed against rules set by a native speaker.
  No real customer data. DeepSeek's terms allow training other models on its output.
- **Format:** Gemma's own chat template with thinking off. Each conversation is shown twice: once with the empty
  thinking block at the start of each turn, training only each turn's first move, and once as the template replays
  it, training only the moves after a tool result. Every trained position therefore matches its test prompt exactly.
  The loss covers only the receptionist's words, tool calls and end-of-turn tokens.
- **Recipe:** QLoRA on the 4-bit (NF4) base, LoRA rank 16, alpha 32, dropout 0.05, all linear layers; learning rate
  2e-4, cosine schedule; batch 1 with 16 accumulated; 4 passes (524 steps), about 3.5 hours on one RTX 5080 (9.3 GB
  of GPU memory). Twelve checkpoints were compared on the 40-case dev set and a greeted copy of it, by a rule fixed in
  advance; checkpoint 440 was chosen (39/40 and 39/40).
- **GGUF:** the adapter merged into the 16-bit base while converting (llama.cpp), Q8_0, then Q4_K_M from Q8_0.

## Limits

- The tests are synthetic: test v1's customer messages were reviewed by one native speaker, test v2's were drafted by
  an LLM from that speaker's style choices and AI-reviewed. Real customers write with more variety.
- Each test case is one decision, not a whole conversation. Multi-turn reliability is not yet measured.
- Scores check tools and facts. Whether the replies sound naturally Saudi has not yet been judged in the project's
  blind native-speaker review.
- It invents a fact now and then (3 of 160 fresh cases, mostly dates). In production, check every price, time and date
  a reply states against the tool results before sending it.
- Built for receptionist work at small Saudi businesses; not tested on anything else.

## Licence

Apache-2.0, as the base model ([Gemma 4 licence](https://ai.google.dev/gemma/docs/gemma_4_license)). Built by Basel
([GitHub](https://github.com/<github-user>)).
