"""Minimal localhost HTTP façade over the live single-question generator.

Bridges the Python generator (generate_one) to the Next.js frontend's 10-question
JIT flow. Stateless: the frontend passes area/excludePis per call, so there is no
session state to manage. The Next route handler proxies to this (PY_GEN_URL).

Run:
    source venv/bin/activate
    python backend/test-gen-model/src/py_gen_service.py
    # or: PY_GEN_PORT=8000 python .../src/py_gen_service.py

Endpoints:
    GET  /health            -> { "ok": true, "clusters": [...], "levels": [...] }
    POST /generate-question -> BankQuestion (application/json)
        body: { cluster, level, difficulty, area?, excludePis?: string[] }

Env mirrors the generator (OLLAMA_API_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE, ...).
Bound to 127.0.0.1 — localhost only; no static/bank path ever invokes the model.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# generate_test.py lives in ./generators and there is no package __init__, so add
# that directory to the path and import it as a top-level module.
sys.path.insert(0, str(Path(__file__).resolve().parent / "generators"))

import generate_test as gen  # noqa: E402

HOST = os.environ.get("PY_GEN_HOST", "127.0.0.1")
PORT = int(os.environ.get("PY_GEN_PORT", "8000"))

MAX_BODY_BYTES = 64 * 1024  # excludePis of ~10 short strings is well under this.


class Handler(BaseHTTPRequestHandler):
    # Quieter, single-line request logging.
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[py-gen] {self.address_string()} - {fmt % args}\n")

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Harmless for the same-origin Next proxy; convenient for direct dev calls.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "clusters": list(gen.CLUSTERS.keys()),
                    "levels": gen.DIFFICULTY_LEVELS,
                    "difficulties": gen.DIFFICULTY_TIERS,
                    "backend": gen.LLM_BACKEND,
                    "model": gen.active_model_name(),
                },
            )
            return
        self._send_json(404, {"error": f"no route GET {self.path}"})

    def do_POST(self):
        if self.path.rstrip("/") != "/generate-question":
            self._send_json(404, {"error": f"no route POST {self.path}"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "missing or oversized request body"})
            return

        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send_json(400, {"error": f"invalid JSON body: {e}"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "body must be a JSON object"})
            return

        cluster = body.get("cluster")
        level = body.get("level")
        difficulty = body.get("difficulty")
        area = body.get("area")
        exclude_pis = body.get("excludePis", [])

        # Validate before touching the model so bad requests fail fast and clearly.
        if cluster not in gen.CLUSTERS:
            self._send_json(400, {"error": f"unknown cluster '{cluster}'"})
            return
        if level not in gen.DIFFICULTY_LEVELS:
            self._send_json(
                400, {"error": f"level must be one of {gen.DIFFICULTY_LEVELS}"}
            )
            return
        if difficulty not in gen.DIFFICULTY_TIERS:
            self._send_json(
                400, {"error": f"difficulty must be one of {gen.DIFFICULTY_TIERS}"}
            )
            return
        if area is not None and not isinstance(area, str):
            self._send_json(400, {"error": "area must be a string"})
            return
        if not isinstance(exclude_pis, list) or not all(
            isinstance(p, str) for p in exclude_pis
        ):
            self._send_json(400, {"error": "excludePis must be a string[]"})
            return

        try:
            question = gen.generate_one(
                cluster_key=cluster,
                level=level,
                difficulty=difficulty,
                area=area,
                exclude_pis=tuple(exclude_pis),
            )
        except ValueError as e:  # bad area / enum -> client error
            self._send_json(400, {"error": str(e)})
            return
        except Exception as e:  # model/parse failure -> server error
            self._send_json(502, {"error": f"generation failed: {e}"})
            return

        self._send_json(200, question)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[py-gen] live single-question service on http://{HOST}:{PORT}")
    if gen.LLM_BACKEND == "ollama":
        print(f"[py-gen] backend=ollama model={gen.OLLAMA_MODEL} via {gen.OLLAMA_API_URL}")
    else:
        print(f"[py-gen] backend={gen.LLM_BACKEND} model={gen.active_model_name()}")
    print("[py-gen]   POST /generate-question   GET /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[py-gen] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
