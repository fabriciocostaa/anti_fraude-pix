"""Mocks de demonstracao. Nao conectam ao Serasa ou ao Banco Central."""
import json
import os
import re
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROVIDER = os.environ.get("MOCK_PROVIDER", "serasa")
TOKEN = os.environ.get("INTERNAL_TOKEN", "default_token")
RANGES_PATH = Path(__file__).resolve().parent / "income_ranges.json"
if not RANGES_PATH.exists():
    RANGES_PATH = Path(__file__).resolve().parents[1] / "src" / "income_ranges.json"
RANGES = json.loads(RANGES_PATH.read_text(encoding="utf-8"))
CALLS = Counter()
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path.strip("/")
        if path == "health_check":
            return self.respond(200, {"provider": PROVIDER, "simulated": True})
        if self.headers.get("INTERNAL-TOKEN") != TOKEN:
            return self.respond(403, {"error": "internal_token_required"})
        parts = path.split("/")
        if len(parts) != 2 or not re.fullmatch(r"[0-9]{11}|[A-Z0-9]{12}[0-9]{2}", parts[1]):
            return self.respond(404, {"error": "not_found"})
        route, document = parts
        if route == "calls":
            with LOCK:
                count = CALLS[document]
            return self.respond(200, {"calls": count})
        if route != ("income" if PROVIDER == "serasa" else "fraud-markers"):
            return self.respond(404, {"error": "not_found"})
        with LOCK:
            CALLS[document] += 1
        suffix = int(document[-2:])
        if suffix == 99:
            return self.respond(503, {"error": "simulated_unavailable"})
        if PROVIDER == "serasa":
            income = None if suffix == 98 else RANGES[suffix % len(RANGES)]["label"]
            return self.respond(200, {"income": income})
        if suffix == 97:
            return self.respond(200, {"unexpected": True})
        marker = None
        if suffix in (1, 2, 3, 98):
            marker = {"tax_id_number": "00000000000" if suffix == 98 else document,
                      "status": "CANCELLED" if suffix == 2 else "REGISTERED",
                      "fraud_type": "OTHER" if suffix == 3 else "MULE_ACCOUNT"}
        return self.respond(200, {"fraud_marker": marker})

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
