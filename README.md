# saudi-dialect

Fine-tuning a small open model (about 7–9B parameters) with QLoRA on one consumer GPU (RTX 5080, 16 GB) so that it:

1. writes natural Saudi dialect the way a friendly receptionist texts on WhatsApp, and
2. calls tools correctly (price lookup, available times, booking) in the same conversation.

The goal is to beat both the untuned base model and a strong API baseline on a held-out test set, judged by a blind A/B dialect review from a native speaker plus automatic tool-call checks.

## Status

| Stage | What | Status |
|---|---|---|
| 0 | Big picture, machine check, repo setup | Done |
| 1 | Training environment on the RTX 5080 | Done (smoke test passes) |
| 2 | Base model choice | Done: [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it) (Apache-2.0) |
| 3 | Task spec: businesses, tools, style switches, data format | Done: [docs/TASK_SPEC.md](docs/TASK_SPEC.md) |
| 4 | Test set: 160 test + 40 dev cases, native-speaker reviewed, frozen | Done: [docs/TEST_SET.md](docs/TEST_SET.md) |

Nothing below this line is claimed until it is done and verified. Results, dataset card and model card will be added when they exist.

## Findings so far

**Stage 2: choosing the base model.** Measured on our own Saudi-dialect text and on this GPU, not taken from vendor claims.

| Candidate | Tokens per word (Saudi probe) | Tool-call template | QLoRA peak VRAM at 1,024 tokens | Seconds per training step |
|---|---|---|---|---|
| ALLaM-7B-Instruct-preview | 1.79 | none | - | - |
| **Gemma-4-12B-it** | **2.22** | yes | **14.6 GB** | **7.8** |
| Fanar-1-9B-Instruct | 2.33 | none | - | - |
| Qwen3.5-9B | 2.34 | yes | 14.8 GB | 12.6 |
| Granite-4.2-8B | 4.21 | yes | - | - |

In a blind A/B test on 10 customer messages, judged by a native speaker before any fine-tuning, Gemma-4-12B-it won 9 and Qwen3.5-9B won 0 (1 tie). This is a small sample from one judge, used only to choose the base model. Details: [LEARNING.md](LEARNING.md#step-2--choosing-the-base-model), raw outputs in [`results/stage2/`](results/stage2/).

**Stage 4: the test set.** 160 test and 40 dev cases across 12 categories (prices, bookings with date phrases, cancellations, handoffs, closed hours, small talk, pressure tests, and a tool the model never sees in training). Each case is a conversation up to one decision plus the correct next step, scored automatically, with 42 cases for a blind native-speaker dialect review. Frozen on 2026-09-30:

| File | SHA-256 |
|---|---|
| `data/test/test_v1.jsonl` | `6fc684b157e5719567ba347525a26bc62a6646755a089c3f7393341b1d41935f` |
| `data/test/dev_v1.jsonl` | `6d1a148fe416b8d167ec0f50374ef86f4c78971ebd4e970f6b00a8aa5b095f8b` |

Check them with `sha256sum data/test/*_v1.jsonl`. Any change to the test set becomes a new version (`test_v2`), never a silent edit.

**Known limitations so far.** The test messages are synthetic drafts reviewed and edited by one native speaker, so their phrasing is less varied than real customers. The dialect verdicts come from one judge.

## Roadmap (plan, not results)

This is a comparison study as much as a fine-tune. The question is not only "did fine-tuning help?" but "is fine-tuning a small local model worth it compared with prompting strong models?"

| Stage | Plan |
|---|---|
| 2 | Choose the base model: licence, Arabic quality, tokenizer efficiency on Saudi text, tool-call support, fits QLoRA in 16 GB |
| 3 | Task spec: fictional businesses, tool schema, style switches (casual/formal, warm/plain, emoji on/off) |
| 4 | Test set, written from scratch before any training data, then frozen |
| 5 | Benchmark harness: one script runs any model over the test set and scores it the same way. Competitors: API models with one shared prompt, other open Arabic models, and the base model with a prompt and with few-shot examples |
| 6 | Training data: licence audit, synthetic generation only where terms allow, native-speaker review, leakage check against the test set |
| 7 | QLoRA training on the RTX 5080 |
| 8 | Evaluation: automatic tool-call checks, blind A/B dialect review, confidence intervals, cost and speed per reply |
| 9 | Publish: results table, raw outputs per model, side-by-side conversation gallery, dataset card, model card with honest limitations |
| Later | The same data on a larger model in the cloud; other regional dialects, each with its own test set |

Fairness rules for the comparison: every model gets the same prompt; the prompt is tuned on the validation set and frozen before any test results exist; each API's terms are checked before its outputs are published.

## Reproduce

Tested on Windows 11, RTX 5080 (16 GB, sm_120), NVIDIA driver 610.88, with [uv](https://docs.astral.sh/uv/).

```bash
git config core.hooksPath .githooks   # enable the commit-message guard (once per clone)
uv sync                               # Python 3.12 + torch 2.12.1+cu130 + training libraries, from uv.lock
uv run python scripts/smoke_test.py   # GPU, sm_120 kernels, 4-bit, and a tiny QLoRA training run
```

## Learning log

This is also a learning project. See [LEARNING.md](LEARNING.md) for each step explained, and [GLOSSARY.md](GLOSSARY.md) for the terms.

## Licence

Code: [Apache-2.0](LICENSE). Datasets and model weights will carry their own licences, recorded per source.
