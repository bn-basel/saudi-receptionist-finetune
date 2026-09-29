"""Stage 2b: does QLoRA on this model fit in 16 GB, and how fast does it train?

Loads the real model in 4-bit, adds LoRA adapters the way we will in Stage 7, and
runs a few training steps on one sequence of --seq tokens. Content does not matter
for memory or speed, so the tokens are random.

Reports: VRAM after loading, peak VRAM during training, seconds per step, tokens/sec.

Run: uv run python scripts/bakeoff_memory.py <hf_repo_id> [--seq 2048] [--steps 5]
"""

import argparse
import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

OUT = Path(__file__).resolve().parent.parent / "results" / "stage2" / "bakeoff"
GB = 2**30


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_id")
    parser.add_argument("--seq", type=int, default=2048)
    parser.add_argument("--steps", type=int, default=5)
    args = parser.parse_args()

    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,  # also compress the scale table (standard QLoRA)
            bnb_4bit_compute_dtype=torch.bfloat16,
        ),
        dtype=torch.bfloat16,
        device_map={"": 0},
    )
    load_s = time.time() - t0
    loaded_gb = torch.cuda.memory_allocated() / GB
    print(f"loaded {type(model).__name__} in {load_s:.0f}s, VRAM {loaded_gb:.2f} GB")

    model = prepare_model_for_kbit_training(
        model, gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules="all-linear",
        exclude_modules=r".*(vision|visual|audio).*",  # text layers only
    ))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"LoRA trainable parameters: {trainable:,} ({trainable / total:.2%} of the loaded model)")

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
    vocab = model.get_input_embeddings().num_embeddings
    batch = torch.randint(0, vocab, (1, args.seq), device="cuda")
    model.train()
    torch.cuda.reset_peak_memory_stats()

    step_times = []
    for step in range(args.steps + 1):  # step 0 is a warm-up and is not timed
        torch.cuda.synchronize()
        t = time.time()
        loss = model(input_ids=batch, labels=batch).loss
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        torch.cuda.synchronize()
        if step > 0:
            step_times.append(time.time() - t)
        print(f"step {step}: loss {loss.item():.3f}, {time.time() - t:.2f}s")

    peak_gb = torch.cuda.max_memory_allocated() / GB
    total_gb = torch.cuda.get_device_properties(0).total_memory / GB
    result = {
        "model": args.model_id,
        "seq_len": args.seq,
        "vram_after_load_gb": round(loaded_gb, 2),
        "peak_vram_training_gb": round(peak_gb, 2),
        "gpu_total_gb": round(total_gb, 2),
        # On Windows the driver silently borrows system RAM when VRAM runs out, which is
        # 10-100x slower instead of crashing. A peak this close to the total means it spilled.
        "fits_in_vram": peak_gb < 0.95 * total_gb,
        "seconds_per_step": round(sum(step_times) / len(step_times), 2),
        "tokens_per_second": round(args.seq / (sum(step_times) / len(step_times))),
        "lora_trainable_params": trainable,
        "load_seconds": round(load_s),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"memory__{args.model_id.replace('/', '__')}__seq{args.seq}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
