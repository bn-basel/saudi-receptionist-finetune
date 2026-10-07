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
3. **The way people run it.** The same practice set through llama-server's OpenAI-style chat API
   (`--model llamachat:<url>@<repo>`, the GGUF's own template and tool parser, as in LM Studio) and through Ollama
   (`--model ollama:<name>@<repo>`, with the Modelfiles in `release/allam/` and `release/gemma/`).
4. **A real conversation.** `release/demo/` runs the model with the benchmark's fake backend and shows each tool call.

| | ALLaM-7B | Gemma-4-12B |
|---|---|---|
| Re-test, test v1: original / Q8_0 / Q4_K_M | 131 / 129 / 134 | 151 / 154 / 153 |
| Re-test, greeted test v1: original / Q8_0 / Q4_K_M | 147 / 146 / 149 | 153 / 154 / 148 |
| Q4_K_M, greeted, through llama-server's chat API (as LM Studio) | 152 | 148 |
| Q4_K_M, greeted, through Ollama | 145 | 149 |
| GGUF template = training prompt | 320 of 320 | 320 of 320 |
| Speed, Q4_K_M on the RTX 5080 | 0.5 s per reply | 0.7 s per reply |
| Demo: price → slots → booking | works (3 correct tool calls) | works (3 correct tool calls) |

Differences of a few cases between versions are within noise (a 160-case score moves by several points from chance
alone). One lean worth stating: Gemma's Q4_K_M scores 148 on greeted test v1 against 153-154 for the original and
Q8_0 (p = 0.18 against the original). Q8_0 is the recommended Gemma file. A false alarm, for the record: a hand-made
`/tokenize` test showed two start-of-text tokens, but over 160 real chat requests llama-server never added a second
one, and its chat API scores the same as the exact route.

## Publishing (Basel)

1. Log in once: `uv run hf auth login` (the token stays with you; `uv run` uses the project's copy of the tool).
2. Create two model repositories, for example `bnbasel/saudi-receptionist-gemma-4-12b` and
   `bnbasel/allam-7b-saudi-receptionist`, and upload the adapter files, the two GGUF files, the model card as
   `README.md`, the Modelfile, and for ALLaM `allam_tools.py`:
   ```bash
   uv run hf upload bnbasel/allam-7b-saudi-receptionist runs/allam_v1/checkpoint-414 . --include "adapter_*"
   uv run hf upload bnbasel/allam-7b-saudi-receptionist C:/WIP/release-work/allam-7b-saudi-receptionist/gguf . --include "*.gguf"
   uv run hf upload bnbasel/allam-7b-saudi-receptionist release/allam .
   ```
3. The model cards already use these names: `bnbasel` on Hugging Face and `bn-basel/mujawib-receptionist-finetune` on GitHub.
