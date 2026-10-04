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
| **Kernel (GPU)** | A small program compiled for one GPU architecture. A library without kernels for sm_120 fails on the RTX 5080 with "no kernel image is available". |
| **CUDA runtime vs toolkit** | The runtime is the library programs need to use the GPU (PyTorch ships its own copy). The toolkit (`nvcc`) is only for compiling new GPU code. |
| **Wheel** | A pre-built Python package file (`.whl`). PyTorch publishes a separate wheel per CUDA version, such as `cu130`. |
| **Package index** | A server that `pip`/`uv` download packages from. PyPI is the default; PyTorch runs its own index for GPU builds. |
| **Virtual environment** | A project-private folder (`.venv`) of Python packages, so projects do not break each other. |
| **Lockfile** | `uv.lock`: the exact version of every package installed, so anyone can recreate the same environment. |
| **NF4** | "NormalFloat 4-bit": the 4-bit format QLoRA uses, with its 16 levels spaced to suit the bell-shaped spread of model weights. |
| **bitsandbytes** | The library that stores weights in 4-bit and runs the maths on them. |
| **PEFT** | Hugging Face's library for adding LoRA adapters to a model. |
| **TRL** | Hugging Face's library with ready-made training loops, such as `SFTTrainer`. |
| **Triton** | A compiler for writing custom GPU kernels in Python. Used by speed-up libraries like Unsloth; not needed by the plain stack. |
| **WSL2** | Windows Subsystem for Linux: a real Linux running inside Windows, with GPU access. Our fallback if native Windows fails. |
| **Fertility** | Average tokens per word for a tokenizer on some text. Lower is better. On our Saudi probe it ranged from 1.79 (ALLaM) to 4.21 (Granite). |
| **Derivative work** | Something made from someone else's work, such as a fine-tune of a base model. It must follow the base model's licence. |
| **Apache-2.0** | A permissive licence: use, modify, publish and sell, as long as you keep the licence and notices and mark your changes. Includes a patent grant. |
| **Mixture of experts (MoE)** | A model with many "expert" sub-networks, of which only a few run per token ("35B-A3B" = 35B total, 3B active). Fast to run, but all experts must fit in memory to fine-tune. |
| **Sysmem fallback** | A Windows NVIDIA driver behaviour: when VRAM is full, it silently borrows system RAM instead of failing. The job keeps running, but 10–100× slower. |
| **Blind test** | Judging outputs without knowing which system produced them, so expectations cannot bias the verdict. |
| **Sign test** | A simple check of whether a win count could be luck: if two systems were equal, each decisive pick is a coin flip. |
| **Catastrophic forgetting** | When fine-tuning on a narrow task makes a model worse at everything else. |
| **Synthetic data** | Training examples written by a model instead of people. Cheap and fully controllable, but only as good as the filters it passes. |
| **Teacher / student** | The teacher is a strong model that writes the training examples; the student is the smaller model trained on them. |
| **Context distillation** | The teacher answers with a long, detailed prompt; the student is trained on those answers with a short prompt, so it learns to act as if it had read the long one. |
| **Customer simulator** | A model call that plays the customer, so generated conversations have realistic back-and-forth. |
| **Few-shot examples** | Example replies placed in a prompt to show the style wanted. Models copy them closely, mistakes included. |
| **False positive / false negative** | A check that rejects something good / lets something bad through. Both have to be measured. |
| **Pilot** | A small trial run (here 50 conversations) to find problems cheaply before scaling up. |
| **Yield** | The share of generated examples that end up usable after checks and review. |
| **Checkpoint** | A snapshot of the trained adapter saved during training, so different amounts of training can be compared afterwards. |
| **Loss mask** | Marking which tokens the model is graded on during training. Here only the receptionist's own words and tool calls; the customer and the tool results are masked out. |
| **Dev set** | A small practice set used to make choices (prompts, checkpoints). The test set is kept for the one final measurement. |
| **Selection bias** | Choosing among many options by their test scores picks the one that got lucky, so its score overstates its real skill. |
| **Learning curve** | Score plotted against the amount of training or data; shows where more stops helping. |
| **Epoch / pass** | One time through all the training examples. |
| **Back-test (of a check)** | Running a new automatic check over data people already reviewed before trusting it: it should catch the rows they rejected and leave the rows they passed alone. |
| **Regression test** | A test written from a bug that was found, so the same mistake is caught automatically if it ever comes back. |
| **Logits** | The model's raw score for every word in its vocabulary, at every position. For Gemma 4 that is 262,144 numbers per token, so the full table for a long conversation takes gigabytes. |
| **Scores only where trained** | Building logits only at the positions the loss mask grades (17% of tokens here), with the same loss and gradients. It cut run 2's peak memory from 13.5 GB to 9.6 GB. |
| **System-memory fallback (VRAM spill)** | When a Windows GPU runs out of its own memory, it borrows ordinary RAM. Nothing fails, but every step becomes several times slower; a slow step is the warning sign. |
| **Noise floor** | How much a result changes when you repeat the same computation. A difference is only meaningful if it is bigger than this. |
| **Test leakage** | When the test set influences a decision (for example, choosing a fix by reading test failures). The test then stops being a fresh exam, and its score is a little too good. |
| **First move** | The receptionist's first action after a customer message: a reply, a tool call or a handoff. Grading whole conversations can miss a wrong first move that is fixed later in the conversation. |
| **Small multiples** | A chart split into several small panels, one per series, with the same axes, so lines don't pile on top of each other. |
