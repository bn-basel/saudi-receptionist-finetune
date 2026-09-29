"""Stage 2: compare candidate base models by their tokenizer and chat template.

Downloads only tokenizer and template files (a few MB per model), never weights.

For each model it measures:
  1. Fertility: tokens per word on our own Saudi-dialect probe messages. Fewer is
     better: cheaper, faster, and more text fits in the context window.
  2. How one message is split into tokens, so you can see it with your own eyes.
  3. Tool-call support in the chat template: renders a short conversation with a
     tool definition, a tool call and a tool result, and checks that all three
     survive into the text the model would actually see. The rendered text is
     saved so you can read it.

Run: uv run python scripts/compare_tokenizers.py <hf_repo_id> [<hf_repo_id> ...]
"""

import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "data" / "probe" / "saudi_messages.txt"
OUT = ROOT / "results" / "stage2"

# A fictional clinic, used only to exercise the chat template (not training or test data).
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_service_price",
        "description": "Look up the price of a service in Saudi riyals.",
        "parameters": {
            "type": "object",
            "properties": {"service": {"type": "string", "description": "Service name"}},
            "required": ["service"],
        },
    },
}]
CONVERSATION = [
    {"role": "system", "content": "أنتِ موظفة استقبال في عيادة أسنان خيالية."},
    {"role": "user", "content": "كم سعر تنظيف الأسنان؟"},
    {"role": "assistant", "tool_calls": [{"type": "function", "function": {
        "name": "get_service_price", "arguments": {"service": "تنظيف الأسنان"}}}]},
    {"role": "tool", "name": "get_service_price", "content": json.dumps({"price": 250, "currency": "SAR"})},
    {"role": "assistant", "content": "تنظيف الأسنان بـ250 ريال. تبين أحجز لك موعد؟"},
]


def load_probe() -> list[str]:
    lines = [l.strip() for l in PROBE.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


def fertility(tok, messages: list[str]) -> tuple[int, int]:
    tokens = sum(len(tok.encode(m, add_special_tokens=False)) for m in messages)
    words = sum(len(m.split()) for m in messages)
    return tokens, words


def template_check(tok, model_id: str) -> str:
    try:
        text = tok.apply_chat_template(CONVERSATION, tools=TOOLS, tokenize=False)
    except Exception as e:  # templates without tool support often raise here
        return f"error: {type(e).__name__}"
    safe_name = model_id.replace("/", "__")
    (OUT / "templates").mkdir(parents=True, exist_ok=True)
    (OUT / "templates" / f"{safe_name}.txt").write_text(text, encoding="utf-8")
    checks = {
        "tool definition": "Look up the price" in text,
        "tool call": text.count("get_service_price") >= 2,
        "tool result": "250" in text,
    }
    missing = [k for k, ok in checks.items() if not ok]
    return "all present" if not missing else "missing: " + ", ".join(missing)


def main(model_ids: list[str]) -> None:
    messages = load_probe()
    sample = messages[0]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for model_id in model_ids:
        print(f"\n=== {model_id}")
        try:
            tok = AutoTokenizer.from_pretrained(model_id)
        except Exception as e:
            print(f"  could not load tokenizer: {type(e).__name__} (gated? needs licence accepted + HF login)")
            rows.append((model_id, "-", "-", "-", "not loaded"))
            continue
        tokens, words = fertility(tok, messages)
        pieces = tok.convert_ids_to_tokens(tok.encode(sample, add_special_tokens=False))
        print(f"  vocab {len(tok):,} | {tokens} tokens for {words} words -> {tokens / words:.2f} tokens/word")
        print(f"  '{sample}' -> {len(pieces)} tokens")
        print(f"  decoded pieces: {[tok.convert_tokens_to_string([p]) for p in pieces]}")
        status = template_check(tok, model_id)
        print(f"  tool-call template: {status}")
        rows.append((model_id, f"{len(tok):,}", str(tokens), f"{tokens / words:.2f}", status))

    table = ["| Model | Vocab | Tokens | Tokens/word | Tool-call template |", "|---|---|---|---|---|"]
    table += [f"| {' | '.join(r)} |" for r in rows]
    (OUT / "tokenizers.md").write_text(
        f"Probe: {len(messages)} messages, {sum(len(m.split()) for m in messages)} words\n\n"
        + "\n".join(table) + "\n", encoding="utf-8")
    print("\n" + "\n".join(table))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
