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
BASE_DIR = Path(__file__).resolve().parent
SERASA_DATA = json.loads((BASE_DIR / "serasa.json").read_text(encoding="utf-8"))
DICT_DATA = json.loads((BASE_DIR / "dict.json").read_text(encoding="utf-8"))
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
        if PROVIDER == "serasa":
            return self.respond(200, SERASA_DATA)
        marker = DICT_DATA.get("fraud_marker")
        if marker and str(marker.get("tax_id_number")) == str(document):
            return self.respond(200, {"fraud_marker": marker})
        return self.respond(200, {"fraud_marker": None})

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()

