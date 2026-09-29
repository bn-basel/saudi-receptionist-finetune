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

**What I learned.** _(filled in after the Step 1 check questions)_
