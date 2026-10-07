# Release: how the public model files are made and checked

Two models are released, each as a LoRA adapter (small; needs the base model) and as GGUF files (one file, runs in
llama.cpp, LM Studio or Ollama):

| Model | Adapter | GGUF Q8_0 | GGUF Q4_K_M | Model card |
|---|---|---|---|---|
| Gemma-4-12B, run 6, checkpoint 440 | `runs/gold_v6/checkpoint-440` (380 MB) | 11.8 GB | 6.9 GB | [release/gemma/README.md](../release/gemma/README.md) |
| ALLaM-7B, checkpoint 414 | `runs/allam_v1/checkpoint-414` (231 MB) | 6.9 GB | 4.0 GB | [release/allam/README.md](../release/allam/README.md) |

## Building the GGUF files

```bash
uv run python scripts/export_gguf.py --model gemma --adapter runs/gold_v6/checkpoint-440 --name saudi-receptionist-gemma-4-12b
uv run python scripts/export_gguf.py --model allam --adapter runs/allam_v1/checkpoint-414 --name allam-7b-saudi-receptionist
```

llama.cpp build b11457 (Windows, CUDA 13.4) does the conversion. The adapter is merged into each weight as the
converter reads it (W + alpha/r · B·A, in float32), so no merged copy is written to disk; the first version did write
one and ran out of disk on Gemma. Both ways give the same weights: rebuilt with each, ALLaM's 291 tensors are byte for
byte identical. Q8_0 comes straight from the converter and Q4_K_M from Q8_0.

## Checks before any score is quoted

1. **Same prompts, different weights.** `scripts/run_eval.py --model llamacpp:<url>@<repo>` renders every prompt with
   the original tokenizer, exactly as for the original evaluation, and sends token ids to llama-server, so a re-test
   measures only the GGUF file. It runs on the practice sets (test v1 as written and greeted), not on test v2, so the
   fresh exam is not used again.
2. **The file's own chat template.** Apps build the prompt from the template stored in the GGUF, not from this
   repository. `scripts/check_gguf_template.py` asks llama-server to render every practice case and compares it with
   the training prompt, character by character.
3. **A real conversation.** `release/demo/` runs the model with the benchmark's fake backend and shows each tool call.

| | ALLaM-7B | Gemma-4-12B |
|---|---|---|
| Re-test, test v1: original / Q8_0 / Q4_K_M | 131 / 129 / 134 | 151 / pending / pending |
| Re-test, greeted test v1: original / Q8_0 / Q4_K_M | 147 / 146 / 149 | 153 / pending / pending |
| GGUF template = training prompt | 320 of 320 | pending |
| Demo: price → slots → booking | works (3 correct tool calls) | pending |

Differences of a few cases between versions are within noise (a 160-case score moves by several points from chance
alone).

## Publishing (Basel)

1. Log in once: `hf auth login` (the token stays with you).
2. Create two model repositories, for example `<hf-user>/saudi-receptionist-gemma-4-12b` and
   `<hf-user>/allam-7b-saudi-receptionist`, and upload the adapter files, the two GGUF files, the model card as
   `README.md`, and for ALLaM `allam_tools.py`:
   ```bash
   hf upload <hf-user>/allam-7b-saudi-receptionist runs/allam_v1/checkpoint-414 . --include "adapter_*"
   hf upload <hf-user>/allam-7b-saudi-receptionist C:/WIP/release-work/allam-7b-saudi-receptionist/gguf . --include "*.gguf"
   hf upload <hf-user>/allam-7b-saudi-receptionist release/allam .
   ```
3. Replace `<hf-user>` and `<github-user>` in the model cards and the README links.
