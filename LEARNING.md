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

## Step 6 — Training data: generate, check, review

**Concept.** No public dataset has Saudi receptionist conversations with our tools in them, so the training conversations are generated. A strong **teacher** model (DeepSeek V4.1 Flash, whose licence allows training other models on its outputs) plays the receptionist with the long, fully explained prompt; a second call plays the **customer**; the fake backend answers the tool calls. The student (Gemma) will later be trained with the short prompt on the teacher's replies, so it learns to behave as if it had read the long rules (context distillation). Generated text is only as good as its filters, so every conversation passes two gates: **automatic checks** in code (cheap, run on everything, catch rule breaks) and a **review** against written rules (catches what code cannot: unnatural wording, contradictions). Every recurring review note becomes either a teacher rule or a new check, and the loop repeats on a small pilot before anything is scaled up.

**What we did.**
- Licence audit of every candidate source ([docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)): most public Saudi datasets were excluded (generated by models whose terms forbid it, scraped, unlicensed or Modern Standard Arabic). The one usable human-written source, Voho's Najdi dialogues, is kept for a Stage 7 comparison.
- 40 training businesses ([spec/train_businesses.json](spec/train_businesses.json)), separate from the 4 test businesses, so the test stays unseen.
- The generator ([scripts/datagen.py](scripts/datagen.py)) and its checks, each backed by a unit test ([scripts/test_datagen.py](scripts/test_datagen.py), 138 cases): exact times and days against the tools and the clock, time-of-day words, the salaam, the formal opener, gender, claimed actions, past slots, placeholder names, Modern Standard Arabic, the teacher's own reasoning leaking into a reply, and leakage against the test set.
- Three 50-conversation pilots. Usable after review: pilot_v1 14 of 49 (29%, formal rows 1 of 23), pilot_v2 15 of 43 (35%), pilot_v3 33 of 39 (85%). The review rules (decisions v1–v4) were written by Basel after blind calibration rounds; an AI reviewer applies them, and Basel decides every rule and spot-checks each batch.
- The full run started: batch 1 of `train_v1` kept 82 of 100 conversations for $0.09. Each batch of 100 is reviewed before the next one is generated.

**What I learned.**
- A model copies its examples more than it follows its rules. The prompt said "formal opens with «حياك الله»", yet 17 of 23 formal rows copied an example that opened with «هلا والله». Later, a rule's own example («عطني اسمك الكريم») was copied at women-only businesses, where it is wrong. Examples have to obey every rule, or not be there.
- A prompt is a request; a check is a guarantee. Rewording the prompt lowers an error rate, but only a check in code removes the error from the data, and it also counts how often the model still makes it.
- Checks have false positives too. Every round, reading the rejected conversations found checks that threw out good ones (half of the rejections in pilot_v2, 6 of 24 in batch 1): a name matched inside another word («وعد» in «موعد»), a prefix hid a phrase («لبعد بكرة»), a spelling variant was missed («نوره»). A wrong check does not just waste rows; it silently removes a whole kind of correct sentence from the training data.
- Checks tuned on the reviewed pilots look better on those pilots than they will on new data. The honest test is the next batch: how many of the reviewer's rejections the checks did not catch.
- When a rule is hard for people to state precisely, it is hard for a model too. Time-of-day words tied to prayer times kept producing edge cases, so the rule became a simple clock rule (morning before 12:00, evening after).


## Step 7 — First fine-tuning run (QLoRA on the reviewed data)

**Concept.** QLoRA keeps Gemma's 12 billion weights frozen in 4-bit and trains small add-on matrices (LoRA adapters) beside them; a checkpoint is just those add-ons (~400 MB). Each training example is a whole conversation rendered exactly as the benchmark renders it (short prompt, tools, Gemma's own chat template), but the model is only graded on what the receptionist writes: its replies, its tool calls and the two tokens that end its turn. The customer's lines and the tool results are masked out, so the model learns to act, not to predict customers. Checkpoints are saved along the way and compared on the **dev** set (40 cases, used for choices); the chosen one is measured once on the **test** set (160 cases, never used for choices).

**What we did.**
- Wrote [scripts/train.py](scripts/train.py): 348 "gold" conversations (reviewed ok and passing today's checks; 331 train, 17 held back), max 1,536 tokens, LoRA rank 16 on all linear layers, learning rate 2e-4, 4 passes, a checkpoint every 15 steps. Checked the loss mask by printing one example with the trained parts in brackets.
- The first smoke test ran at 228 s per step: `prepare_model_for_kbit_training` turns the non-4-bit weights, including Gemma's 262k-token embedding table, into float32, which pushed the GPU to 17.2 GB on a 16 GB card and Windows spilled into system memory. Keeping them in bf16 gave 12.9 GB and ~1.8 s per conversation. The full run took 33 minutes.
- Added adapter loading to the benchmark (`hf:<model>@<adapter folder>`) and scored all 12 checkpoints on dev: 75% after less than half a pass, then a plateau around 80–90% from about two passes on (untuned: 37.5%). Fixed the tie-break rule before touching the test set (best dev score, then lowest held-back error) → checkpoint 150.
- Test set, run once: **143/160 = 89.4%** (95% CI 84–93%), against 40.6% untuned and 87.5–94.4% for the API models.

**What I learned.**
- The first thing fine-tuning taught was the tool-calling habit, not the dialect: after less than half a pass the dev score had doubled, and prices and bookings went from 0 to almost all correct. Prompting could not do this in Stage 5.
- Choose on dev, measure once on test, and write the selection rule down before looking. Trying several candidates on test and keeping the best is the lottery ticket again.
- With 40 cases, three cases is noise: checkpoints that tie at 36/40 fail on different cases. The shape of a curve is trustworthy; single differences are not.
- The model learns the data's habits, good and bad. It hands off every unknown question (12/12, where DeepSeek gets 4/12), but on complaints it apologises and says it will pass it on without calling the tool, because many training complaints did that. Better data on that one behaviour fixes it; more of the same data would not.
- Fine-tuning narrows as well as teaches: with a tool it never saw in training (`reschedule_booking`), the tuned model fell back on the procedure it was trained on (check slots first) and scored lower than before (9 → 7 of 10).

## Step 7b — Run 2: more data (and a crashed PC)

**The question.** Run 1 trained on 352 conversations. By now I had 874 reviewed ones. Same model, same settings, only more data: does it get better?

**What happened.**
- The first try was very slow: about 60 seconds a step instead of 12. The card was full, so Windows started borrowing normal RAM. I tried a few quick fixes, stopped and restarted the run three times, and the PC blue-screened during the night. Lesson: a slow step is a warning. Stop and find the cause; don't keep poking a GPU that is already struggling.
- The real cause: at the end, the model gives a score to every word in its vocabulary (262,144 of them) for every token in the conversation. For one long conversation that is gigabytes. But we only train on about 17% of the tokens (the receptionist's own words). The other 83% of those scores were calculated and then thrown away.
- The fix: only calculate the scores where the model is actually graded. Same loss, same learning, much less memory. I checked it first: the loss matched to six digits, and the gradients differed by about as much as the old code differs from itself when you run it twice. Peak memory went from 13.5 GB to 9.6 GB.
- Then a second, smaller problem: memory crept up again during the run. PyTorch keeps old memory blocks in a cache "just in case", and on Windows the card counts everything a program holds, not just what it is using. A cap on that cache fixed it, and the run resumed from its last checkpoint instead of starting over.
- Dev set: run 2 reached 40/40 after about 2.4 passes and stayed there for six checkpoints in a row. Run 1 never got above 36/40.
- Test set, run once: **148/160 = 92.5%**, up from 89.4%. That is level with GPT-5.4 mini and 3 cases behind DeepSeek V4.1 Flash.

**What I learned.**
- More good data helped, but not as much as the dev score suggested. 40/40 on dev turned into 92.5% on test. Dev is small (40 cases) and it was used to pick the checkpoint, so it flatters. That is why the test set exists.
- A +5 gain is not automatically real. Run 2 fixed 11 test cases and broke 6. A paired test (McNemar) says that could still be chance (p = 0.33). The steadier evidence is the dev curve: flat at the top instead of jumping around.
- Before trusting "the numbers are a bit different", measure how different they are when nothing changes. That is the noise floor.
- Most of the GPU memory went to work we threw away. Knowing where the memory goes beat guessing at settings.
- The weak spots are now clear and specific: closed days (it checks slots instead of saying "we're closed"), questions nobody can answer (it searches instead of handing off) and complaints. That tells me what data to make next, rather than just more of everything.
