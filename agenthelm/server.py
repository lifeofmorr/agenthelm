"""AgentHelm local console server (Python stdlib only).

Run:
    python3 -m agenthelm.server                 # discover real sessions
    python3 -m agenthelm.server --demo          # fixture fleet
    python3 -m agenthelm.server --port 7788

Routes:
    GET  /                              fleet board (HTML)
    GET  /api/fleet                     fleet snapshot (JSON)
    GET  /api/brief/<session_id>        handoff brief (markdown)
    POST /api/approvals/<id>/decide     {"decision": "approved"|"denied"|"answered", "answer": "..."}
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters import default_adapters
from .briefs import generate_brief
from .dashboard import render_dashboard
from .scanner import ApprovalsStore, FleetScanner


def make_server(scanner: FleetScanner, store: ApprovalsStore,
                host: str = "127.0.0.1", port: int = 7788) -> ThreadingHTTPServer:

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, render_dashboard().encode("utf-8"),
                           "text/html; charset=utf-8")
                return
            if path == "/api/fleet":
                self._json(200, scanner.scan())
                return
            if path.startswith("/api/brief/"):
                session_id = urllib.parse.unquote(path[len("/api/brief/"):])
                snap = scanner.scan()
                for sess in snap["sessions"]:
                    if sess["id"] == session_id:
                        self._send(200, generate_brief(sess).encode("utf-8"),
                                   "text/plain; charset=utf-8")
                        return
                self._json(404, {"error": "session not found"})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            prefix = "/api/approvals/"
            if path.startswith(prefix) and path.endswith("/decide"):
                approval_id = urllib.parse.unquote(
                    path[len(prefix):-len("/decide")])
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except Exception:
                    payload = {}
                ok = store.decide(approval_id,
                                  str(payload.get("decision", "")),
                                  str(payload.get("answer", "")))
                self._json(200 if ok else 400,
                           {"ok": ok, "approval_id": approval_id})
                return
            self._json(404, {"error": "not found"})

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(prog="agenthelm.server")
    parser.add_argument("--port", type=int, default=7788)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--demo", action="store_true",
                        help="render the fixture fleet instead of real sessions")
    parser.add_argument("--state", default=None,
                        help="path to the decisions store JSON")
    args = parser.parse_args()

    store = ApprovalsStore(args.state) if args.state else ApprovalsStore()
    scanner = FleetScanner(default_adapters(demo=args.demo), store)
    server = make_server(scanner, store, args.host, args.port)
    print(f"AgentHelm console on http://{args.host}:{args.port} "
          f"({'demo fixtures' if args.demo else 'live discovery'}) — Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
