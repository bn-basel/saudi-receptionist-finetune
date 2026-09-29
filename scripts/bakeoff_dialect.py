"""Stage 2b: blind dialect test of candidate base models, before any fine-tuning.

Three commands:
  generate <hf_repo_id>   The model answers every message in data/bakeoff/customer_messages.txt
                          with the same system prompt. Loads in 4-bit, one model at a time.
  blind <id_1> <id_2>     Shuffles each pair of replies into A/B and writes a blind sheet for you
                          to judge. The answer key goes to a separate file: do not open it.
  reveal <id_1> <id_2>    Reads your picks from the sheet, un-blinds them and tallies the result.

Run: uv run python scripts/bakeoff_dialect.py generate Qwen/Qwen3.5-9B
"""

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "bakeoff"
OUT = ROOT / "results" / "stage2" / "bakeoff"
SHEET = OUT / "blind_sheet.md"
KEY = OUT / ".blind_key.json"


def safe(model_id: str) -> str:
    return model_id.replace("/", "__")


def read_lines(path: Path) -> list[str]:
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


def generate(model_id: str) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    system = (DATA / "system_prompt.txt").read_text(encoding="utf-8").strip()
    messages = read_lines(DATA / "customer_messages.txt")
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model.eval()
    torch.manual_seed(0)

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"replies__{safe(model_id)}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for i, msg in enumerate(messages):
            inputs = tok.apply_chat_template(
                [{"role": "system", "content": system}, {"role": "user", "content": msg}],
                add_generation_prompt=True,
                enable_thinking=False,  # a receptionist answers directly
                return_dict=True,
                return_tensors="pt",
            ).to(model.device)
            with torch.no_grad():
                output = model.generate(**inputs, max_new_tokens=200, do_sample=True,
                                        temperature=0.7, top_p=0.9)
            reply = tok.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            f.write(json.dumps({"i": i, "message": msg, "reply": reply}, ensure_ascii=False) + "\n")
            print(f"[{i + 1}/{len(messages)}] done")  # replies stay hidden until the blind test
    print(f"saved {out_path} (do not open it before judging)")


def load_replies(model_id: str) -> list[dict]:
    path = OUT / f"replies__{safe(model_id)}.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def blind(id_1: str, id_2: str) -> None:
    r1, r2 = load_replies(id_1), load_replies(id_2)
    rng = random.SystemRandom()  # unseeded, so the order cannot be re-derived
    key, parts = [], ["# Blind dialect test\n",
                      "For each message, write A, B, or = (equal) after `Pick:`. "
                      "Judge only: which reply sounds more like a real Saudi receptionist on WhatsApp? "
                      "Optional: add a short note after the pick.\n"]
    for a, b in zip(r1, r2):
        pair = [(id_1, a["reply"]), (id_2, b["reply"])]
        rng.shuffle(pair)
        key.append({"i": a["i"], "A": pair[0][0], "B": pair[1][0]})
        parts.append(f"\n## {a['i'] + 1}. {a['message']}\n\n**A:** {pair[0][1]}\n\n**B:** {pair[1][1]}\n\nPick: \n")
    SHEET.write_text("".join(parts), encoding="utf-8")
    KEY.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"wrote {SHEET} ({len(key)} pairs). The key is in {KEY.name}: do not open it before judging.")


def reveal(id_1: str, id_2: str) -> None:
    key = json.loads(KEY.read_text(encoding="utf-8"))
    picks = re.findall(r"^Pick:[ \t]*(\S*)(.*)$", SHEET.read_text(encoding="utf-8"), flags=re.M)
    if len(picks) != len(key) or any(p[0].upper() not in {"A", "B", "="} for p in picks):
        sys.exit("Every pair needs a pick of A, B or = after 'Pick:'.")
    wins = {id_1: 0, id_2: 0, "equal": 0}
    rows = ["| # | Picked | Note |", "|---|---|---|"]
    for k, (pick, note) in zip(key, picks):
        winner = "equal" if pick == "=" else k[pick.upper()]
        wins[winner] += 1
        rows.append(f"| {k['i'] + 1} | {winner} | {note.strip()} |")
    summary = "\n".join(f"- **{name}**: {n}" for name, n in wins.items())
    text = f"# Blind dialect test: result\n\n{summary}\n\n" + "\n".join(rows) + "\n"
    (OUT / "verdict.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    commands = {"generate": (generate, 1), "blind": (blind, 2), "reveal": (reveal, 2)}
    if len(sys.argv) < 2 or sys.argv[1] not in commands or len(sys.argv) != 2 + commands[sys.argv[1]][1]:
        sys.exit(__doc__)
    fn, _ = commands[sys.argv[1]]
    fn(*sys.argv[2:])
