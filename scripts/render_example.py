"""Stage 3: render one spec conversation through Gemma's chat template and count tokens.

Checks that a realistic conversation (system prompt + tool definitions + a booking
with three tool calls) fits the ~1,024-token training budget measured in Stage 2, and
shows where the tokens go. Saves the rendered text so you can read what Gemma sees.

Run: uv run python scripts/render_example.py [spec/example_conversation.json]
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from transformers import AutoTokenizer

from prompt import build_system_prompt, load_spec

ROOT = Path(__file__).resolve().parent.parent
MODEL = "google/gemma-4-12B-it"
BUDGET = 1024


def main(path: Path) -> None:
    businesses, styles, tools = load_spec()
    record = json.loads(path.read_text(encoding="utf-8"))
    meta = record["meta"]
    business = next(b for b in businesses if b["id"] == meta["business_id"])
    system = build_system_prompt(business, styles, meta["style"],
                                 datetime.fromisoformat(meta["now"]), meta["prayer_times"])
    messages = [{"role": "system", "content": system}] + record["messages"]

    tok = AutoTokenizer.from_pretrained(MODEL)
    count = lambda msgs, t=None: len(tok.apply_chat_template(msgs, tools=t, tokenize=True,
                                                             return_dict=True)["input_ids"])
    system_only = count(messages[:1])
    with_tools = count(messages[:1], tools)
    total = count(messages, tools)

    rendered = tok.apply_chat_template(messages, tools=tools, tokenize=False)
    out = ROOT / "results" / "stage3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "example_rendered.txt").write_text(rendered, encoding="utf-8")

    print(f"system prompt : {system_only:4d} tokens")
    print(f"{len(tools)} tool schemas: {with_tools - system_only:4d} tokens")
    print(f"conversation  : {total - with_tools:4d} tokens ({len(record['messages'])} messages)")
    print(f"total         : {total:4d} / {BUDGET} budget -> {'fits' if total <= BUDGET else 'OVER BUDGET'}"
          f" ({BUDGET - total} tokens left for longer chats)")
    print(f"\nrendered text saved to {out / 'example_rendered.txt'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "spec" / "example_conversation.json")
