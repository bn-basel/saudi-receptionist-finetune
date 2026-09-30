"""Stage 5: model adapters. Each one turns (system prompt, messages, tools) into one step:
    {"text": str | None, "tool_calls": [{"name": ..., "arguments": {...}}], "raw": str}

  oracle        Always answers with the case's first expected option. Only for testing
                the harness: it must score 100%.
  hf:<repo_id>  A local Hugging Face model in 4-bit (the same way it will be trained),
                greedy decoding so every run gives the same output.
"""

import json


class OracleModel:
    name = "oracle"

    def step(self, case: dict, system_prompt: str, tools: list[dict]) -> dict:
        option = case["expect"]["options"][0]
        if option["kind"] == "tool_call":
            args = dict(option["args_exact"])
            for k in option["args_nonempty"]:
                args[k] = "x"
            for k, values in option["args_in"].items():
                args[k] = values[0]
            schema = next(t["function"]["parameters"] for t in tools if t["function"]["name"] == option["tool"])
            for k in schema.get("required", []):
                args.setdefault(k, "")
            return {"text": None, "tool_calls": [{"name": option["tool"], "arguments": args}], "raw": ""}
        parts = ["تمام"]
        parts += [t.split(":")[0] for t in option.get("must_mention_times", [])]
        parts += option["must_include_any"][:1]
        return {"text": " ".join(parts), "tool_calls": [], "raw": ""}


class HFModel:
    """Local model in 4-bit NF4, greedy decoding, thinking switched off."""

    def __init__(self, repo_id: str, max_new_tokens: int = 256):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.name = repo_id
        self.torch = torch
        self.max_new_tokens = max_new_tokens
        self.tok = AutoTokenizer.from_pretrained(repo_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            repo_id,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
            dtype=torch.bfloat16,
            device_map={"": 0},
        )
        self.model.eval()

    def step(self, case: dict, system_prompt: str, tools: list[dict]) -> dict:
        messages = [{"role": "system", "content": system_prompt}] + case["messages"]
        prompt = self.tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True,
                                              enable_thinking=False, tokenize=False)
        inputs = self.tok(prompt, return_tensors="pt", add_special_tokens=False).to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        raw = self.tok.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=False)
        try:
            parsed = self.tok.parse_response(raw, prefix=prompt)
        except Exception as e:  # unparseable output counts as a plain-text reply
            parsed = {"content": raw, "parse_error": f"{type(e).__name__}: {e}"}
        calls = [{"name": tc["function"]["name"], "arguments": tc["function"].get("arguments") or {}}
                 for tc in parsed.get("tool_calls") or []]
        for c in calls:  # some parsers return arguments as a JSON string
            if isinstance(c["arguments"], str):
                try:
                    c["arguments"] = json.loads(c["arguments"])
                except json.JSONDecodeError:
                    pass
        return {"text": parsed.get("content"), "tool_calls": calls, "raw": raw,
                **({"parse_error": parsed["parse_error"]} if "parse_error" in parsed else {})}


def load_model(spec: str):
    if spec == "oracle":
        return OracleModel()
    if spec.startswith("hf:"):
        return HFModel(spec[3:])
    raise ValueError(f"unknown model {spec!r} (use oracle or hf:<repo_id>)")
