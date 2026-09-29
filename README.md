# saudi-dialect

Fine-tuning a small open model (about 7–9B parameters) with QLoRA on one consumer GPU (RTX 5080, 16 GB) so that it:

1. writes natural Saudi dialect the way a friendly receptionist texts on WhatsApp, and
2. calls tools correctly (price lookup, available times, booking) in the same conversation.

The goal is to beat both the untuned base model and a strong API baseline on a held-out test set, judged by a blind A/B dialect review from a native speaker plus automatic tool-call checks.

## Status

| Stage | What | Status |
|---|---|---|
| 0 | Big picture, machine check, repo setup | In progress |

Nothing below this line is claimed until it is done and verified. Results, dataset card and model card will be added when they exist.

## Learning log

This is also a learning project. See [LEARNING.md](LEARNING.md) for each step explained, and [GLOSSARY.md](GLOSSARY.md) for the terms.

## Licence

Code: [Apache-2.0](LICENSE). Datasets and model weights will carry their own licences, recorded per source.
