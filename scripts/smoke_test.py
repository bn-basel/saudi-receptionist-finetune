"""Stage 1 smoke test: can this machine run QLoRA?

No model download. Four checks, each stops the script if it fails:
  1. PyTorch sees the GPU and was built with sm_120 (Blackwell) kernels.
  2. A matrix multiply on the GPU gives the same answer as on the CPU.
  3. bitsandbytes can store weights in 4-bit (NF4) and read them back.
  4. QLoRA in miniature: a tiny, randomly initialised Llama-style model is saved,
     reloaded in 4-bit through the same code path we will use for the real model,
     given LoRA adapters, and trained for a few steps. Only the adapters may learn,
     and the loss must go down.

Run: uv run python scripts/smoke_test.py
"""

import sys
import tempfile

import torch


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        sys.exit(1)


def versions() -> None:
    import bitsandbytes, peft, transformers, trl

    print(f"python {sys.version.split()[0]} | torch {torch.__version__} (CUDA {torch.version.cuda})")
    print(f"bitsandbytes {bitsandbytes.__version__} | transformers {transformers.__version__} | "
          f"peft {peft.__version__} | trl {trl.__version__}\n")


def gpu_and_kernels() -> None:
    check("GPU visible to PyTorch", torch.cuda.is_available())
    cap = torch.cuda.get_device_capability()
    check("compute capability 12.0", cap == (12, 0), f"{torch.cuda.get_device_name()} reports {cap}")
    archs = torch.cuda.get_arch_list()
    check("PyTorch has sm_120 kernels", "sm_120" in archs, " ".join(archs))


def matmul_matches_cpu() -> None:
    torch.manual_seed(0)
    a, b = torch.randn(512, 512), torch.randn(512, 512)
    on_gpu = (a.cuda() @ b.cuda()).cpu()
    diff = (on_gpu - a @ b).abs().max().item()
    check("GPU matmul matches CPU", diff < 0.05, f"max difference {diff:.1e}")


def four_bit_round_trip() -> None:
    import bitsandbytes.functional as F

    w = torch.randn(4096, 4096, dtype=torch.bfloat16, device="cuda")
    packed, state = F.quantize_4bit(w, quant_type="nf4")
    restored = F.dequantize_4bit(packed, state)
    rel_err = ((restored - w).float().norm() / w.float().norm()).item()
    mb_16 = w.numel() * w.element_size() / 2**20
    mb_4 = packed.numel() * packed.element_size() / 2**20
    # NF4 keeps 16 levels per weight, so each weight is rounded: ~10% error is expected.
    check("4-bit NF4 store and read back", rel_err < 0.15,
          f"{mb_16:.0f} MB in 16-bit -> {mb_4:.0f} MB in 4-bit, relative error {rel_err:.1%}")


def tiny_qlora_training() -> None:
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, LlamaConfig, LlamaForCausalLM
    import bitsandbytes as bnb

    torch.manual_seed(0)
    config = LlamaConfig(vocab_size=1000, hidden_size=256, intermediate_size=512,
                         num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=4)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        LlamaForCausalLM(config).save_pretrained(tmp)  # random weights, a few MB, local only
        model = AutoModelForCausalLM.from_pretrained(
            tmp,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            ),
            device_map={"": 0},
        )

    n_4bit = sum(isinstance(m, bnb.nn.Linear4bit) for m in model.modules())
    check("model loaded with 4-bit layers", n_4bit > 0, f"{n_4bit} Linear4bit layers")

    model = prepare_model_for_kbit_training(
        model, gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, target_modules="all-linear",
                                             task_type="CAUSAL_LM"))
    trainable = {n for n, p in model.named_parameters() if p.requires_grad}
    total = sum(p.numel() for p in model.parameters())
    n_train = sum(p.numel() for n, p in model.named_parameters() if n in trainable)
    check("only LoRA adapters are trainable", all("lora_" in n for n in trainable),
          f"{n_train:,} of {total:,} parameters trainable")

    # One fixed batch of random token ids; the model should learn to predict it.
    batch = torch.randint(0, config.vocab_size, (4, 64), device="cuda")
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-3)
    model.train()
    losses = []
    for _ in range(40):
        loss = model(input_ids=batch, labels=batch).loss
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        losses.append(loss.item())

    check("loss goes down with LoRA on a 4-bit model", losses[-1] < 0.8 * losses[0],
          f"{losses[0]:.2f} -> {losses[-1]:.2f}")
    print(f"\npeak VRAM used by this test: {torch.cuda.max_memory_allocated() / 2**20:.0f} MB")


if __name__ == "__main__":
    versions()
    gpu_and_kernels()
    matmul_matches_cpu()
    four_bit_round_trip()
    tiny_qlora_training()
    print("\nAll checks passed: this machine can run QLoRA.")
