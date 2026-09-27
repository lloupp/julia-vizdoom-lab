from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from minecraft_shadow import MINECRAFT_ACTIONS, MinecraftJuliaShadow


class Handler(BaseHTTPRequestHandler):
    shadow: MinecraftJuliaShadow
    threshold: float = 0.75

    def log_message(self, fmt, *args):
        print("[julia-minecraft-shadow] " + (fmt % args))

    def send_json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False, default=lambda o: o.__dict__).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"status": "ok", "profile": "minecraft", "shadow": True})
        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/v1/minecraft/decision":
            return self.send_json(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(size) or b"{}")
            state = body.get("state")
            if not isinstance(state, dict):
                raise ValueError("state deve ser objeto")
            available = body.get("available_actions", list(MINECRAFT_ACTIONS))
            if not isinstance(available, list):
                raise ValueError("available_actions deve ser lista")
            check = self.shadow.invariance_check(state, available)
            forward = check["forward"]
            eligible = (
                check["stable"]
                and forward.valid
                and forward.confidence >= self.threshold
            )
            self.send_json(200, {
                "action": forward.action,
                "confidence": forward.confidence,
                "probabilities": forward.probabilities,
                "latency_ms": forward.latency_ms + check["reverse"].latency_ms,
                "stable": check["stable"],
                "eligible": eligible,
                "trusted": False,
                "shadow": True,
                "error": forward.error,
            })
        except Exception as exc:
            self.send_json(400, {"error": f"{type(exc).__name__}: {exc}", "trusted": False, "shadow": True})


def main():
    parser = argparse.ArgumentParser(description="Julia-1 Minecraft shadow server")
    parser.add_argument("--model-dir", default="models/Julia-1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threshold", type=float, default=0.75)
    args = parser.parse_args()

    from julia import load_model

    engine = load_model(
        args.model_dir,
        device=args.device,
        strict_encoding=True,
        max_length=8192,
        head_length=512,
    )
    Handler.shadow = MinecraftJuliaShadow(engine)
    Handler.threshold = args.threshold
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Julia Minecraft shadow http://{args.host}:{args.port}/v1/minecraft/decision")
    server.serve_forever()


if __name__ == "__main__":
    main()
