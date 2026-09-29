# Glossary

Short, plain definitions. Added to as each step introduces new terms.

| Term | Meaning |
|---|---|
| **Token** | The unit a model reads and writes: a word, part of a word, or a symbol. Arabic often splits into more tokens than English, which makes it slower and more expensive. |
| **Parameters / weights** | The numbers inside the model that training adjusts. "8B" means about 8 billion of them. |
| **Pretraining** | The original, very expensive training on huge amounts of text that teaches a model language in general. We do not do this. |
| **Fine-tuning** | Continuing training on a small, focused dataset to change the model's behaviour. |
| **Prompting** | Changing behaviour only by what you write in the input, without changing any weights. |
| **SFT (supervised fine-tuning)** | Fine-tuning on example conversations where we show the exact reply we want. |
| **Loss** | A number measuring how wrong the model's predictions are on the training examples. Training tries to make it smaller. |
| **LoRA** | Low-Rank Adaptation: freeze the original weights and train small add-on matrices instead. The result is a small "adapter" file. |
| **Adapter** | The small set of trained LoRA weights, stored separately from the base model and applied on top of it. |
| **Quantization** | Storing numbers with fewer bits (for example 4 bits instead of 16) to save memory, at a small cost in precision. |
| **QLoRA** | LoRA on top of a base model that is quantized to 4 bits. Makes fine-tuning a 7–9B model fit in 16 GB. |
| **VRAM** | The GPU's own memory. The model, the training state and the activations must all fit in it. |
| **Chat template** | The exact text format (with special tokens) a model uses to mark system, user, assistant and tool turns. Fine-tuning data must use the base model's own template. |
| **Tool calling** | The model outputs a structured request (usually JSON) naming a tool and its arguments; our code runs the tool and feeds the result back. |
| **Train / validation / test split** | Train: what the model learns from. Validation: used during training to watch for problems. Test: kept locked away and used only for the final score. |
| **Overfitting** | The model memorises the training examples instead of learning the pattern, so it looks great on training data and worse on new data. |
| **Data leakage** | Test examples (or near-copies) ending up in training data, which makes the scores dishonestly high. |
| **Baseline** | What we compare against: here the untuned base model and a strong API model. |
| **CUDA** | NVIDIA's platform for running general computation on the GPU. PyTorch uses it to train models. |
| **Compute capability** | NVIDIA's version number for a GPU's feature set. The RTX 5080 is 12.0 (Blackwell, "sm_120"); software must be built to support it. |
| **Commit trailer** | A `Key: value` line at the end of a git commit message, such as `Co-authored-by:`. GitHub shows co-author trailers as extra contributors. |
| **Git hook** | A script git runs at a certain moment. A `commit-msg` hook can inspect a commit message and refuse the commit. |
