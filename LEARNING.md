# Learning log

One entry per step: the concept in one paragraph, what we did, and what I learned. Terms are defined in [GLOSSARY.md](GLOSSARY.md).

---

## Step 0 — Big picture, machine check, repo setup

**Concept.** A language model is a very large function that reads tokens and predicts the next one; its "knowledge" and "style" live in billions of numbers called weights. Fine-tuning means continuing to train those weights on our own examples (here: Saudi receptionist conversations with tool calls) so the model's default behaviour shifts toward them. Training all 8 billion weights needs roughly 16 bytes of GPU memory per weight (weights, gradients, optimizer state), about 128 GB, far more than a 16 GB card. LoRA freezes the original weights and trains two small matrices per layer whose product is added on top, so only about 0.5% of the numbers are trained. QLoRA also stores the frozen original weights in 4-bit form (about 5 GB for an 8B model), which is what makes the whole job fit in 16 GB. We will know it worked only by measuring on a test set the model never saw during training, and comparing against the untuned base model and an API model.

**What we did.**
- Checked the machine: RTX 5080 (16 GB, compute capability 12.0 = Blackwell), driver 610.88, CUDA toolkit 12.8, Python 3.11–3.14 available through `uv`, 31 GB RAM, about 120 GB free on C:, WSL not installed.
- Created the repo and added a `commit-msg` git hook that refuses any `Co-authored-by` or "Generated with" line, so every commit has a single author.
- Made the first commit and checked `git log` for trailers.

**What I learned.** _(filled in after the Step 0 check questions)_
