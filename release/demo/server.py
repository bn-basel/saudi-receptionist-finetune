"""Local demo: chat with a fine-tuned receptionist and watch its tool calls change a fake clinic's calendar.

1. Serve a GGUF build with llama.cpp:
       llama-server -m allam-7b-saudi-receptionist-Q4_K_M.gguf -ngl 99 -c 4096 --port 8082
2. Start this demo (from the repository root) and open http://127.0.0.1:8766:
       uv run python release/demo/server.py --model allam --server http://127.0.0.1:8082
       uv run python release/demo/server.py --model gemma --server http://127.0.0.1:8082

It uses the benchmark's own code (scripts/models.py LlamaCppModel): the prompt is rendered exactly as in training and
testing, and the tools run against the same deterministic fake backend (scripts/backend.py). Nothing leaves the PC.
"""

import argparse
import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from backend import Backend  # noqa: E402
from models import LlamaCppModel  # noqa: E402
from prompt import build_system_prompt, load_spec  # noqa: E402

REPOS = {"gemma": "google/gemma-4-12B-it", "allam": "humain-ai/ALLaM-7B-Instruct-preview"}
LABELS = {"gemma": "Gemma-4-12B, fine-tuned (run 6)", "allam": "ALLaM-7B, fine-tuned"}
PRAYER = {"Asr": "15:12", "Maghrib": "17:41", "Isha": "19:11"}  # Riyadh, early October
STYLE = {"register": "casual", "warmth": "warm", "emoji": "off"}
MAX_STEPS = 5  # tool calls the model may chain before it has to answer


class Session:
    def __init__(self, business: dict):
        self.business = business
        self.backend = Backend(business, {})
        self.messages: list[dict] = []
        self.calls = 0


def run_turn(model, session: Session, styles: dict, tools: list[dict], text: str) -> list[dict]:
    """One customer message -> the events of the receptionist's turn: tool calls, their results, the reply."""
    system = build_system_prompt(session.business, styles, STYLE, datetime.now(), PRAYER, "short")
    session.messages.append({"role": "user", "content": text})
    events = []
    for _ in range(MAX_STEPS):
        step = model.step({"messages": session.messages}, system, tools)
        if step.get("tool_calls"):
            call = step["tool_calls"][0]  # one at a time, as in training
            session.calls += 1
            cid = f"call_{session.calls}"
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            result = session.backend.call(call.get("name") or "", args)
            session.messages.append({"role": "assistant", "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": call.get("name"), "arguments": args}}]})
            session.messages.append({"role": "tool", "tool_call_id": cid, "name": call.get("name"),
                                     "content": json.dumps(result, ensure_ascii=False)})
            events += [{"type": "tool_call", "name": call.get("name"), "arguments": args},
                       {"type": "tool_result", "name": call.get("name"), "result": result}]
            continue
        reply = (step.get("text") or "").strip() or "…"
        session.messages.append({"role": "assistant", "content": reply})
        events.append({"type": "reply", "text": reply})
        return events
    events.append({"type": "reply", "text": "(stopped after too many tool calls in a row)"})
    return events


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Arabic names on a Windows console
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=REPOS, required=True)
    ap.add_argument("--server", default="http://127.0.0.1:8082", help="llama-server URL")
    ap.add_argument("--business", default="dental_clinic", help="an id from spec/businesses.json")
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()

    businesses, styles, tools = load_spec()
    business = next(b for b in businesses if b["id"] == args.business)
    model = LlamaCppModel(args.server, REPOS[args.model])
    sessions: dict[str, Session] = {}
    lock = threading.Lock()  # one generation at a time: llama-server is single-GPU
    page = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code: int, body: bytes, kind: str):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                return self.send(200, page.encode(), "text/html; charset=utf-8")
            if self.path == "/api/info":
                info = {"model": LABELS[args.model], "business": business["name"], "assistant": business["assistant"]["name"],
                        "hours": business["hours"], "services": [{"name": s["name"], "price": s["price_sar"]} for s in business["services"]]}
                return self.send(200, json.dumps(info, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            self.send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/chat":
                return self.send(404, b"not found", "text/plain")
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            sid, text = str(body.get("session", "")), str(body.get("message", "")).strip()
            if body.get("reset") or sid not in sessions:
                sessions[sid] = Session(business)
            if not text:
                return self.send(200, b"[]", "application/json")
            with lock:
                events = run_turn(model, sessions[sid], styles, tools, text)
            self.send(200, json.dumps(events, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    print(f"demo: http://127.0.0.1:{args.port}  ({LABELS[args.model]} via {args.server}, {business['name']})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
