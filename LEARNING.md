# Learning log

One entry per step: the concept in one paragraph, what we did, and what I learned. Terms are defined in [GLOSSARY.md](GLOSSARY.md).

---

## Step 0 — Big picture, machine check, repo setup

**Concept.** A language model is a very large function that reads tokens and predicts the next one; its "knowledge" and "style" live in billions of numbers called weights. Fine-tuning means continuing to train those weights on our own examples (here: Saudi receptionist conversations with tool calls) so the model's default behaviour shifts toward them. Training all 8 billion weights needs roughly 16 bytes of GPU memory per weight (weights, gradients, optimizer state), about 128 GB, far more than a 16 GB card. LoRA freezes the original weights and trains two small matrices per layer whose product is added on top, so only about 0.5% of the numbers are trained. QLoRA also stores the frozen original weights in 4-bit form (about 5 GB for an 8B model), which is what makes the whole job fit in 16 GB. We will know it worked only by measuring on a test set the model never saw during training, and comparing against the untuned base model and an API model.

**What we did.**
- Checked the machine: RTX 5080 (16 GB, compute capability 12.0 = Blackwell), driver 610.88, CUDA toolkit 12.8, Python 3.11–3.14 available through `uv`, 31 GB RAM, about 120 GB free on C:, WSL not installed.
- Created the repo and added a `commit-msg` git hook that refuses any `Co-authored-by` or "Generated with" line, so every commit has a single author.
- Made the first commit and checked `git log` for trailers.

**What I learned.**
- Full fine-tuning costs about 16 **bytes** (not bits) per parameter: 8B × 16 B ≈ 128 GB, far above my 16 GB.
- LoRA freezes **all** of the original weights and trains *new* small add-on matrices (about 0.5% of the size); it does not pick some original weights to train.
- I first missed QLoRA's second half: the frozen weights are stored in **4-bit**, which shrinks them from about 16 GB to about 5 GB. Freezing (LoRA) plus 4-bit storage (Q) is what makes it fit.
- The test set is written before the training data to stop **leakage**: if I write test cases after seeing the training data, they end up resembling it, and the score measures memory instead of skill. Baselines are a separate idea (Stage 5): they use the test set, but they are not the reason it comes first.

---

## Step 1 — Training environment on the RTX 5080

**Concept.** Training runs on a stack of layers: GPU → NVIDIA driver → CUDA runtime (bundled inside the PyTorch download) → PyTorch → bitsandbytes (4-bit weights) → transformers / PEFT / TRL (model, LoRA adapters, training loop). Code for the GPU is compiled into *kernels* for specific architectures, and the RTX 5080 (Blackwell, compute capability 12.0) needs every layer to ship **sm_120** kernels, or it fails with "no kernel image is available". So before installing, we checked each layer's actual build, not just its announcements.

**What we did.**
- Researched the current support (29 Sep 2026): PyTorch 2.14 is the latest stable, with Windows CUDA 13.0 wheels; the bitsandbytes 0.50.2 build script compiles its Windows wheels for sm_120; Unsloth works on Windows but with fragile version pins and tested torch only up to 2.12.1; vLLM has no native Windows.
- Chose **native Windows** with the plain Hugging Face stack (no Unsloth for now): nothing to install at system level, every piece supports sm_120, and plain Python moves to Linux cloud GPUs unchanged. WSL2 is the fallback if we need vLLM or Unsloth.
- Pinned Python 3.12 and torch 2.12.1+cu130 (tested by both bitsandbytes and Unsloth) in `pyproject.toml`; `uv.lock` records every exact version.
- Wrote `scripts/smoke_test.py` and ran it. All checks passed:
  - PyTorch sees the RTX 5080 and has sm_120 kernels.
  - A GPU matrix multiply matches the CPU exactly.
  - A 4096×4096 weight matrix goes from 32 MB (16-bit) to 8 MB (4-bit NF4), with 9.2% rounding error per weight.
  - A tiny random Llama-style model loaded in 4-bit, with LoRA on all linear layers: only the 69,632 adapter parameters are trainable (5.6% here; about 0.5% on an 8B model, because big layers grow faster than their adapters), and the loss fell from 7.01 to 3.35 in 40 steps. Peak VRAM: 201 MB.
- Harmless warning noted: "triton not found" only disables flop counting; we chose not to install Triton.

**What I learned.**
- The smoke test used a **separate tiny model**, not a piece of the 8B one. It proves the *pipeline* works on this GPU: the sm_120 kernels, 4-bit loading, LoRA adapters, the backward pass and the optimizer. It does **not** prove that an 8B model fits in 16 GB, how fast training will be, or anything about quality. Those get checked in Stages 2 and 7.
- PyPI's torch for Windows is CPU-only. The CUDA builds live on PyTorch's own server, with one build per CUDA version (`cu130`). Without it, the version would read `+cpu` and the very first check, "GPU visible to PyTorch", would have failed.

---

## Step 2 — Choosing the base model

**Concept.** The base model sets the ceiling for everything after it, and its licence decides what we may publish, because a fine-tune is a derivative of its base. Four things matter here. (1) **Licence:** Apache-2.0 allows modifying, publishing and commercial use, as long as the licence and notices are kept. (2) **Tokenizer fertility:** how many tokens a model needs per word of Saudi text; fewer means faster, cheaper, and more conversation per example. (3) **Chat template:** the exact text format a conversation becomes; if it has a slot for tools, the model already knows a tool-call format we can build on. (4) **Fit:** in QLoRA the whole model must sit in VRAM. For a mixture-of-experts (MoE) model that means *all* experts, not just the active ones, which is why the newest giant models (DeepSeek V4, GLM-5, Kimi K3, Qwen3.8) can only be competitors, not bases.

**What we did.**
- Scanned current open models from the Hugging Face API (general families, Chinese labs, Arabic-first models). Everything newer than Qwen3.5 in the Qwen family is 27B+ or MoE, too big for 16 GB. Mistral and Jais-2 were dropped by decision; Falcon-H1-Arabic is not openly published.
- Measured tokenizers on a 30-message Saudi probe (generated with Mujawib, reviewed by me, kept out of git). Tokens per word: ALLaM-7B 1.79, Gemma-4-12B 2.22, Fanar-1-9B 2.33, Qwen3.5-9B 2.34, Granite-4.2-8B 4.21. ALLaM and Fanar have no tool support in their template (it crashes when a tool turn appears). Dialect words like `أبغى` get split by every tokenizer, while formal words stay whole: a visible sign of MSA-heavy training data.
- Bake-off between Qwen3.5-9B and Gemma-4-12B-it (both Apache-2.0, both with tool templates):
  - **Memory and speed** (4-bit, LoRA r=16 on all linear layers, batch 1): at 1,024 tokens both fit (Qwen 14.8 GB, 12.6 s/step; Gemma 14.6 GB, 7.8 s/step). At 2,048 tokens neither fits (Qwen 18.2 GB, Gemma 19.3 GB). On Windows the driver silently borrows system RAM instead of crashing, so running out of VRAM shows up as extreme slowness (Qwen: 180 s/step). Qwen is also slowed by the missing fast kernels for its linear-attention layers.
  - **Blind dialect test:** 10 customer messages, same system prompt, A/B order shuffled per message, answer key hidden until I had judged. Gemma 9, Qwen 0, one tie leaning Gemma. A sign test puts 9–0 by luck at about 0.4%. Qwen drifted into Egyptian and Levantine forms and invented facts; Gemma's mistakes were claiming availability without checking, assuming today's date, and promising a location it did not have, all things tool calling should fix.
- **Decision: `google/gemma-4-12B-it`**, Apache-2.0 (standard text, confirmed on Google's licence page). It won on dialect, tokenizer efficiency and speed, and it has a native tool-call format. Constraint for later stages: training examples of about 1,024 tokens unless Stage 7 finds memory savings.

**What I learned.**
- The missing fast kernels (the "environment") made Qwen slower at *every* length, but they cannot explain the jump from 12.6 to 180 s/step. The jump came from running out of VRAM: at 2,048 tokens Qwen needed 18.2 GB on a 15.9 GB card, so Windows moved the overflow into system RAM and the GPU spent most of its time waiting for data over the PCIe bus. Twice the text should cost about twice the time; the rest was the spill. So on Windows, a sudden huge slowdown is a memory warning, not a speed problem.
- Shuffling A/B separately for every message does two jobs a fixed order cannot. It stops **position bias** (people lean toward the first or the second option regardless of content), and it stops me from **recognising a model by its style** after a few messages and effectively un-blinding the test.

---

## Step 3 — Task spec: businesses, tools, style switches, data format

**Concept.** Before creating any data we fix the contract every later stage follows. The model never runs a tool: it only *writes* a request such as `call:get_available_slots{...}`. Our code runs it (a fake calendar built from `spec/` while we develop and evaluate; a real booking system in production), puts the result back into the conversation, and the model then writes its reply from that result. Tools are described with JSON Schema, and those descriptions are part of every conversation, so they cost tokens every time. Style switches work by *conditioning*: a line in the system prompt states the style, and training on many conversations with different values teaches the model to follow that line, so the tone can change without retraining.

**What we did.**
- Wrote [docs/TASK_SPEC.md](docs/TASK_SPEC.md): 4 fictional businesses (clinic, salon, car wash, restaurant), 6 tools, the expected tool sequence for each scenario, 5 checkable hard rules, 3 style switches (register, warmth, emoji), and the data format. Records store only the ingredients of the system prompt (business, style, time), and [scripts/prompt.py](scripts/prompt.py) rebuilds it, so the wording can improve later without regenerating data.
- Put today's date, weekday and prayer times into the system prompt, fixing the bake-off mistake of guessing the day and letting the model turn "الخميس بعد العشا" into a real date and time.
- Measured the budget with Gemma's own template: the first draft was 1,267 tokens (over the 1,024 that fit). Trimming the tool descriptions, dropping `reschedule_booking` and shortening the rules brought the reference conversation to 1,009 tokens. Stage 7 will look for memory savings to allow longer chats.
- Decisions: general Saudi dialect for v1 (regional dialects later), masculine forms by default (always feminine at the women-only salon), and `reschedule_booking` kept out of training entirely but put in the test set as an *unseen tool*.
- Reviewed the Arabic as a native speaker: corrected the style examples and the reference conversation.

**What I learned.**
- Between the model's `call:` line and its reply, *our* code runs the tool and inserts the result. The model only ever writes text. An "invented fact" is a price or time the model writes that never came from a tool result or the system prompt: it skipped the call, or ignored the result, and filled the gap from patterns in its weights.
- Keeping `reschedule_booking` out of training is not about stopping it from inventing times. It is a **generalisation test**, like an exam question of a type the class never practised. If the model uses a tool it has never seen correctly, just from its definition, it has learned to *read* tool definitions, which means new tools can be added later without retraining. If we trained on it, a correct call would only prove memory, and we would have no evidence for that.

---

## Step 4 — The test set

**Concept.** The test set is the exam behind every claim in the README, so three rules protect it. It is written **before** any training data, so it cannot drift toward what the model practised. It is **frozen**: its SHA-256 fingerprint is published, and changing even one character changes the fingerprint, so anyone can check it was never edited. And it is **never used for tuning**: prompts are tuned on a separate dev set, and the test set is only used for final scores. Each case is a conversation up to one decision plus the one correct next step, so every step of a flow is measured on its own and most checks are automatic (right tool, exact arguments, no invented numbers, emoji switch). At 160 cases, a score of around 80% carries roughly ±6 percentage points of uncertainty.

**What we did.**
- Designed 12 categories (160 test + 40 dev): prices, bookings with date phrases, offering slots, confirming, cancelling, business info, unknown questions, complaints, closed hours, small talk, a tool never seen in training (`reschedule_booking`), and pressure tests.
- Built a deterministic fake backend ([scripts/backend.py](scripts/backend.py)) that answers every tool from `spec/`, and a builder ([scripts/build_testset.py](scripts/build_testset.py)) that assembles each case, validates it and computes the fingerprint.
- The customer messages started as synthetic drafts. I reviewed all 200 rows as a native speaker, with a separate review pass checking dialect, style, gender agreement, tool calls, balance and overlap. That produced 13 rules, for example: no Arabizi anywhere; the assistant writes times with 0–9 and never mixes digit sets; formal replies say الصباح / المساء; customers pick a time in their own words; masculine forms unless the customer is known to be a woman, and always feminine at the women-only salon.
- Some cases accept more than one correct answer, each reported separately. For the unseen tool: using it, the old cancel-and-rebook pattern, or confirming the new time first.
- Checks before freezing: all tool calls valid, no near-duplicate customer lines within a category, overlap with the bake-off and probe messages low, no mixed digits, greetings matching the time of day. Fixed a line-ending issue so the fingerprint matches the file on GitHub on every OS.
- Frozen on 2026-09-30. `test_v1.jsonl` SHA-256 `6fc684b1…1935f`, `dev_v1.jsonl` `6d1a148f…5f8b` (full values in [docs/TEST_SET.md](docs/TEST_SET.md)).

**What I learned.**
- Stopping each case at one decision shows exactly *which* decision the model gets wrong (right tool, wrong date), and it stops one early mistake from spoiling every step after it.
- A frozen test set is never edited, even for a typo found later. Like a published exam, it gets a new version (`test_v2`) with its own fingerprint and a note of what changed, and every model is re-run on the new version; scores from v1 and v2 are never mixed. Otherwise "fixes" made after seeing results could quietly favour my own model.

---

## Step 5 — Benchmark harness and baselines

**Concept.** A benchmark harness turns "is model X good?" into a number anyone can reproduce. For each frozen test case it rebuilds the system prompt, gives the model the conversation so far and the tools, takes its one next step (a tool call or a reply), and scores that step against the expectation. Local models run with greedy decoding (always the most likely token), so the same model gives the same answers every time. Before trusting any score, the scorer itself is tested: a model that always answers correctly must score 100%, and hand-made right and wrong answers must land on the right side. Every score comes with a 95% confidence interval, because 160 cases still leave a few points of uncertainty.

**What we did.**
- Built the scorer ([scripts/scoring.py](scripts/scoring.py)), the model adapters ([scripts/models.py](scripts/models.py)), the runner ([scripts/run_eval.py](scripts/run_eval.py)) and the scorer tests ([scripts/test_scoring.py](scripts/test_scoring.py): the oracle scores 200/200 and 45 hand-made checks pass).
- Read every failure of every model by hand. That found scorer bugs in both directions, fixed in versions 1.1–1.3 and written up in [docs/TEST_SET.md](docs/TEST_SET.md) §5: prices read as times, list numbers counted as invented, digits glued to Arabic letters (`و٨:٣٠`) not read as times, prayer times and the month in a date making invented times look grounded, wrong dates and "تم الحجز" claims not checked at all. The frozen test data never changed, and every model is scored with the same version.
- API competitors run through one OpenRouter key with fixed providers, thinking on and a 2,048-token cap: DeepSeek V4.1 Flash (what Mujawib runs on), GPT-5.4 mini and Gemini 3.8 Flash. Claude was left out on purpose, because the test drafts came from the same model family. Checked each provider's terms first: outputs are ours and benchmarking is allowed.
- A second, long prompt spells out the spec's rules. It was written from the spec only, needed no changes on dev, and was frozen before its test run.
- Results on the test set (short / long prompt): GPT-5.4 mini 92.5 / 98.8%, DeepSeek V4.1 Flash 94.4 / 98.1%, Gemini 3.8 Flash 87.5 / 91.2%, untuned Gemma-4-12B 40.6 / 44.4%, ALLaM-7B 38.1 / 41.9%. All API runs together cost under $0.60.

**What I learned.**
- DeepSeek (151/160) and GPT-5.4 mini (148/160) cannot be called better or worse than each other: 3 cases apart, with overlapping confidence intervals, is within the noise. A real claim needs a gap larger than the uncertainty, or a paired test on the same cases (McNemar's test).
- The long prompt lifted GPT by 6 points but Gemma by only 4, and Gemma still almost never calls a tool. Instructions steer a habit a model already has; they cannot create one it lacks. That is what fine-tuning is for.
- Reading failures by hand is part of measuring. Each round found scorer mistakes that would have made the numbers wrong, sometimes in a model's favour and sometimes against it.

