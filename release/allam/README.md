---
license: apache-2.0
base_model: humain-ai/ALLaM-7B-Instruct-preview
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

# ALLaM-7B Saudi receptionist (tool calling)

HUMAIN's [ALLaM-7B-Instruct-preview](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview), fine-tuned with
QLoRA on one RTX 5080 to work as a **Saudi-dialect WhatsApp receptionist that calls tools**: it looks up prices,
checks free times, books, cancels and hands the conversation to a person.

**Untuned, ALLaM-7B has no tool-calling format. After fine-tuning on 1,153 conversations it made 112 of 113 tool calls
correctly formed and passed 87.5% of a fresh 160-case test, level with GPT-5.4 mini and Gemini 3.8 Flash.**

Part of the open project [saudi-dialect](https://github.com/<github-user>/saudi-dialect): code, training data, both
test sets and every raw result are public there.

## Results

Scored automatically on 160 test cases (one decision each: the right tool with the right arguments, or the right
reply), short system prompt, scorer v1.3. Test v2 uses four businesses that appear in neither training nor test v1.

| Model | Test v2 (95% CI) | Tool calls well-formed | Made-up facts |
|---|---|---|---|
| Gemma-4-12B, fine-tuned the same way ([sister model](https://huggingface.co/<hf-user>/saudi-receptionist-gemma-4-12b)) | 93.8% (89–97%) | 98 / 98 | 3 |
| DeepSeek V4.1 Flash (API) | 92.5% (87–96%) | | 0 |
| GPT-5.4 mini (API) | 91.2% (86–95%) | | 2 |
| Gemini 3.8 Flash (API) | 88.1% (82–92%) | | 0 |
| **This model** | **87.5% (81–92%)** | **112 / 113** | **2** |
| ALLaM-7B-Instruct, untuned (tools described in the prompt) | 40.0% (33–48%) | | 33 |

Against the API models the differences are within chance (paired McNemar test: GPT-5.4 mini p = 0.36,
Gemini p = 1, DeepSeek p = 0.17). By kind of request on test v2: bookings 23/24, cancellations 12/12, complaints
10/10, unknown questions handed to a person 9/12 (DeepSeek 2/12). Weakest: questions the business information
already answers (11/16), where it sometimes hands off instead of answering, and small talk (10/14).

**GGUF builds, re-tested** on the practice copy of test v1 (160 cases, as written and with a greeting added), with
the same prompts as the original:

| Version | Test v1 | Test v1, greeted |
|---|---|---|
| Original (adapter on the 4-bit base, as evaluated) | 131 | 147 |
| GGUF Q8_0 (6.9 GB) | 129 | 146 |
| GGUF Q4_K_M (4.0 GB) | 134 | 149 |

The GGUF's built-in chat template gives exactly the training prompt in 320 of 320 cases (llama-server `--jinja`,
LM Studio). Through the ways people actually run it, Q4_K_M on greeted test v1 scores 152 with llama-server's chat API
and 145 in Ollama with the Modelfile in this repository (the same first move as the exact route in 155 of 160 cases;
Ollama ships its own llama.cpp build, whose arithmetic differs slightly).

## How it calls tools

ALLaM's chat template has no tool format, so the model was trained on a plain-text one:

- the tools are described at the end of the system prompt, after a fixed guide;
- the model calls a tool by replying with one line: `<tool_call>{"name": "...", "arguments": {...}}</tool_call>`;
- your code runs the tool and sends the result back as a user turn: `<tool_result>{...}</tool_result>`.

[`allam_tools.py`](allam_tools.py) (no dependencies) turns OpenAI-style messages and tools into this format and
parses the replies. Use its guide word for word: it is what the model learned.

```python
from allam_tools import to_allam_messages, parse_tool_calls

messages = to_allam_messages(system_prompt, conversation, tools)   # OpenAI-style conversation and tool list
reply = chat(messages)                                              # any server applying ALLaM's chat template
text, calls = parse_tool_calls(reply)                               # [{"name": ..., "arguments": {...}}]
```

## Run it

**LM Studio / llama.cpp:** download `allam-7b-saudi-receptionist-Q4_K_M.gguf` (4.0 GB, fits a laptop) or `Q8_0`.
**Ollama:** put [`Modelfile.allam`](Modelfile.allam) next to the GGUF and run `ollama create allam-saudi-receptionist -f Modelfile.allam`.

```bash
llama-server -m allam-7b-saudi-receptionist-Q4_K_M.gguf -ngl 99 -c 4096 --jinja
```

**Transformers + PEFT** (the adapter in this repository):

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

tok = AutoTokenizer.from_pretrained("humain-ai/ALLaM-7B-Instruct-preview")
model = AutoModelForCausalLM.from_pretrained("humain-ai/ALLaM-7B-Instruct-preview", device_map="auto")
model = PeftModel.from_pretrained(model, "<hf-user>/allam-7b-saudi-receptionist")
prompt = tok.apply_chat_template(to_allam_messages(system_prompt, conversation, tools), add_generation_prompt=True, tokenize=False)
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
`handoff_to_human` ([schemas](https://github.com/<github-user>/saudi-dialect/blob/main/spec/tools.json)). New tools can
be added in the same format; on a tool it never saw in training (`reschedule_booking`) it passed 9 of 10 cases.

## Training

- **Data:** 1,153 receptionist conversations at 40 fictional Saudi businesses (1,095 for training, 58 held back).
  They were drafted on DeepSeek V4.1 Flash by the project's own generation pipeline, under 51 rules written and
  refined through review, then filtered by automatic checks and reviewed against rules set by a native speaker.
  No real customer data. DeepSeek's terms allow training other models on its output.
- **Format:** the text tool format above, rendered with ALLaM's own chat template; the loss covers only the
  receptionist's turns and their end-of-turn token. Every training prompt matches the test prompt exactly.
- **Recipe:** QLoRA on the 4-bit (NF4) base, LoRA rank 16, alpha 32, dropout 0.05, all linear layers; learning rate
  2e-4, cosine schedule; batch 1 with 8 accumulated; 4 passes (548 steps), about an hour on one RTX 5080 (5.4 GB of
  GPU memory). Twelve checkpoints were compared on a 40-case dev set by a rule fixed in advance; checkpoint 414 was
  chosen (37/40).
- **GGUF:** the adapter merged into the 16-bit base, converted to Q8_0 with llama.cpp, then Q4_K_M from Q8_0.

## Limits

- The tests are synthetic: test v1's customer messages were reviewed by one native speaker, test v2's were drafted by
  an LLM from that speaker's style choices and AI-reviewed. Real customers write with more variety.
- Each test case is one decision, not a whole conversation. Multi-turn reliability is not yet measured.
- Scores check tools and facts. Whether the replies sound naturally Saudi has not yet been judged in the project's
  blind native-speaker review.
- It invents a fact now and then (2 of 160 fresh cases). In production, check every price, time and date a reply
  states against the tool results before sending it.
- Built for receptionist work at small Saudi businesses; not tested on anything else.

## Licence

Apache-2.0, as the base model: its Hugging Face page is tagged `apache-2.0` (its card mentions a LICENSE file that is
not present in the repository; checked 2026-10-07). Built by Basel ([GitHub](https://github.com/<github-user>)).
