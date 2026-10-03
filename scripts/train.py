"""Stage 7: QLoRA fine-tuning of Gemma-4-12B-it on the reviewed training conversations.

Each conversation is rendered exactly as the benchmark renders it (scripts/models.py HFModel.step): the short
system prompt, the conversation, and the training copy of the tools, through Gemma's own chat template with
thinking off. The loss covers only what the receptionist writes: its replies, its tool calls, and the two
tokens that end a turn (<|tool_response> after a tool call, <turn|> after a reply). The tool results inside
its turn and everything the customer writes are masked out.

    uv run python scripts/train.py --run gold_v1 --dry-run        # build and measure the data only
    uv run python scripts/train.py --run gold_v1 --max-steps 3    # smoke test: memory and speed
    uv run python scripts/train.py --run gold_v1                  # the real run, checkpoints in runs/gold_v1/

Gold data: conversations the review marked ok that also pass today's automatic checks (older pilot rows that
use «الظهر / العصر» as time labels stay ok in the review but follow an older convention, so they are left out).
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from datagen import OUT_DIR, ROOT, check, train_tools
from prompt import build_system_prompt, load_spec

MODEL = "google/gemma-4-12B-it"
SETS = ["pilot_v1", "pilot_v2", "pilot_v3", "train_v1", "focus_v1", "focus_v2"]
TURN, END = "<|turn>model\n", "<turn|>"
RESPONSE_OPEN, RESPONSE_CLOSE = "<|tool_response>", "<tool_response|>"


def gold_conversations(tok) -> list[dict]:
    from build_testset import trigrams

    businesses = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
    _, styles, tools = load_spec()
    tools = train_tools(tools)
    grams = [trigrams(m["content"]) for f in ("test_v1.jsonl", "dev_v1.jsonl")
             for l in (ROOT / "data" / "test" / f).read_text(encoding="utf-8").splitlines()
             for m in json.loads(l)["messages"] if m["role"] == "user"]
    out, skipped = [], 0
    for name in SETS:
        for l in (OUT_DIR / f"{name}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if r.get("review", {}).get("verdict") != "ok":
                continue
            if check(r, (businesses, styles, tools), tok, grams):
                skipped += 1
                continue
            out.append({**r, "set": name})
    print(f"gold: {len(out)} conversations reviewed ok and passing today's checks ({skipped} ok rows follow an older convention)")
    return out


def render(rec: dict, tok, businesses: dict, styles: dict, tools: list[dict]) -> str:
    meta = rec["meta"]
    system = build_system_prompt(businesses[meta["business_id"]], styles, meta["style"],
                                 datetime.fromisoformat(meta["now"]), meta["prayer_times"], "short")
    order = [next(t for t in tools if t["function"]["name"] == n) for n in meta["tools"]]
    messages = [{"role": "system", "content": system}] + rec["messages"]
    return tok.apply_chat_template(messages, tools=order, tokenize=False, enable_thinking=False)


def trained_spans(text: str) -> list[tuple[int, int]]:
    """Character spans the model learns: each model turn up to and including <turn|>, minus every tool
    result (what follows <|tool_response> up to and including <tool_response|>)."""
    spans, i = [], 0
    while (start := text.find(TURN, i)) != -1:
        start += len(TURN)
        end = text.find(END, start)
        end = len(text) if end == -1 else end + len(END)
        pos = start
        while (r := text.find(RESPONSE_OPEN, pos, end)) != -1:
            spans.append((pos, r + len(RESPONSE_OPEN)))  # the call and the token that stops generation
            close = text.find(RESPONSE_CLOSE, r, end)
            pos = end if close == -1 else close + len(RESPONSE_CLOSE)
        if pos < end:
            spans.append((pos, end))
        i = end
    return spans


def encode(text: str, tok) -> dict:
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    spans = trained_spans(text)
    labels = []
    for tid, (a, b) in zip(enc["input_ids"], enc["offset_mapping"]):
        inside = any(s <= a and b <= e for s, e in spans) and b > a
        labels.append(tid if inside else -100)
    return {"input_ids": enc["input_ids"], "labels": labels}


def build(tok, max_len: int, val_share: float, seed: int) -> tuple[list[dict], list[dict]]:
    businesses = {b["id"]: b for b in json.loads((ROOT / "spec" / "train_businesses.json").read_text(encoding="utf-8"))}
    _, styles, tools = load_spec()
    tools = train_tools(tools)
    rows, too_long = [], 0
    for rec in gold_conversations(tok):
        ex = encode(render(rec, tok, businesses, styles, tools), tok)
        if len(ex["input_ids"]) > max_len:
            too_long += 1
            continue
        rows.append({"id": f"{rec['set']}/{rec['id']}", **ex})
    random.Random(seed).shuffle(rows)
    n_val = max(1, round(len(rows) * val_share))
    val, train = rows[:n_val], rows[n_val:]
    lens = sorted(len(r["input_ids"]) for r in rows)
    trained = sum(sum(1 for x in r["labels"] if x != -100) for r in rows)
    print(f"examples: {len(rows)} (train {len(train)}, validation {len(val)}); dropped over {max_len} tokens: {too_long}")
    print(f"tokens per example: median {lens[len(lens) // 2]}, 90th percentile {lens[int(len(lens) * .9)]}, max {lens[-1]}; "
          f"trained tokens {trained / sum(lens):.0%} of all")
    return train, val


def trained_loss(model, input_ids, labels, num_items_in_batch=None):
    """The causal-LM loss, with vocabulary scores (logits) built only where the loss looks.

    The score at position t predicts token t+1, so position t is kept when labels[t+1] is trained. The other
    ~83% of positions (customer text, tool results) are masked out of the loss anyway, so leaving them out
    changes neither the loss nor the gradients; it only skips a 262k-wide row per position. At ~1,500 tokens
    that table and its float32 copies were 3-4 GB, enough to push run 2 past 16 GB (gold_v2, 3 Oct).
    Same reduction as transformers' default: a sum over trained tokens divided by the number of trained
    tokens in the whole accumulated batch when the Trainer passes it, else a mean."""
    import torch
    keep = (labels[0, 1:] != -100).nonzero().squeeze(-1)  # positions t whose next token is trained
    logits = model(input_ids=input_ids, logits_to_keep=keep).logits[0].float()
    loss = torch.nn.functional.cross_entropy(logits, labels[0, keep + 1], reduction="sum")
    return loss / num_items_in_batch if num_items_in_batch is not None else loss / len(keep)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--max-len", type=int, default=1536)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--accum", type=int, default=8, help="examples per optimizer step (batch size 1)")
    ap.add_argument("--save-every", type=int, default=20, help="optimizer steps between checkpoints")
    ap.add_argument("--max-steps", type=int, default=-1, help="stop early (smoke test)")
    ap.add_argument("--val-share", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true", help="continue from the run's latest checkpoint")
    ap.add_argument("--mem-fraction", type=float, default=0.8,
                    help="cap on the GPU memory PyTorch may hold, cache included (share of the card)")
    args = ap.parse_args()

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    train, val = build(tok, args.max_len, args.val_share, args.seed)
    out = ROOT / "runs" / args.run
    out.mkdir(parents=True, exist_ok=True)
    (out / "data.json").write_text(json.dumps({"train": [r["id"] for r in train], "validation": [r["id"] for r in val],
                                               "args": vars(args)}, indent=1), encoding="utf-8")
    if args.dry_run:
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainerCallback,
                              TrainingArguments)

    # PyTorch keeps freed blocks cached for reuse; with conversations of every length, run 2's cache grew to
    # 15 GB while training used 9.8 GB, and Windows began spilling into system memory (gold_v2, 3 Oct). Under
    # this cap the cache is trimmed first; training itself never needs more than ~10 GB.
    torch.cuda.set_per_process_memory_fraction(args.mem_fraction)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.bfloat16, device_map={"": 0},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",  # as in the benchmark
                                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
    # Not prepare_model_for_kbit_training: it casts every non-4-bit weight to float32, including Gemma's
    # 262k-token embedding table, which pushed the peak to 17.2 GB on a 16 GB card (Windows then spills into
    # system memory and a step takes ~4 minutes). Those weights stay bf16, as at evaluation time.
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05,
                                             target_modules="all-linear", task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    def collate(batch):  # batch size 1: no padding needed
        return {"input_ids": torch.tensor([b["input_ids"] for b in batch]),
                "labels": torch.tensor([b["labels"] for b in batch])}

    class Pace(TrainerCallback):
        """Prints speed and GPU memory, so a slowdown from Windows' system-memory fallback shows at once."""
        def __init__(self):
            self.t0, self.start, self.last = time.time(), None, None

        def on_log(self, a, state, control, logs=None, **kw):
            now = time.time()
            if self.start is None:  # a resumed run starts at its checkpoint's step
                self.start = state.global_step - (a.logging_steps if state.global_step else 0)
            used = torch.cuda.max_memory_allocated() / 2**30
            held = torch.cuda.memory_reserved() / 2**30  # cache included: what Windows counts
            per = (now - self.t0) / max(state.global_step - self.start, 1)
            # the average hides a slowdown that creeps in (gold_v2: 11.4 → 16.1 average while steps took ~24 s)
            recent = (now - self.last[0]) / max(state.global_step - self.last[1], 1) if self.last else per
            self.last = (now, state.global_step)
            left = per * (state.max_steps - state.global_step) / 60
            line = (f"{datetime.now():%H:%M} step {state.global_step}/{state.max_steps}  {per:.1f}s/step  "
                    f"recent {recent:.1f}s/step  ~{left:.0f} min left  peak GPU {used:.1f} GB  held {held:.1f} GB  {logs}")
            print(line, flush=True)
            with open(out / "train.log", "a", encoding="utf-8") as f:  # readable while the run goes on
                f.write(line + "\n")

    class MaskedLogitsTrainer(Trainer):
        """Builds vocabulary scores only at trained positions (see trained_loss); same loss and gradients."""
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            loss = trained_loss(model, inputs["input_ids"].to(model.device), inputs["labels"].to(model.device),
                                num_items_in_batch)
            return (loss, {}) if return_outputs else loss  # evaluation reads only the loss

    trainer = MaskedLogitsTrainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(out), per_device_train_batch_size=1, per_device_eval_batch_size=1,
            gradient_accumulation_steps=args.accum, num_train_epochs=args.epochs, max_steps=args.max_steps,
            learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=5, optim="paged_adamw_8bit",
            bf16=True, logging_steps=1 if args.max_steps > 0 else 5, eval_strategy="steps",
            eval_steps=args.save_every, save_strategy="steps", save_steps=args.save_every, save_total_limit=None,
            report_to="none", seed=args.seed, remove_unused_columns=False, dataloader_num_workers=0,
            prediction_loss_only=True),  # evaluation needs only the loss, not the logits
        train_dataset=Dataset.from_list([{"input_ids": r["input_ids"], "labels": r["labels"]} for r in train]),
        eval_dataset=Dataset.from_list([{"input_ids": r["input_ids"], "labels": r["labels"]} for r in val]),
        data_collator=collate,
        callbacks=[Pace()],
    )
    trainer.train(resume_from_checkpoint=args.resume or None)
    trainer.save_model(str(out / "final"))
    (out / "log_history.json").write_text(json.dumps(trainer.state.log_history, indent=1), encoding="utf-8")
    print(f"done: adapters in {out}")


if __name__ == "__main__":
    sys.exit(main())
