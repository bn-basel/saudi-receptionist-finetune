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

**What I learned.** _(filled in after the Step 2 check questions)_
