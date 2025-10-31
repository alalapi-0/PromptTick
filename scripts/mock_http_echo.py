"""Simple HTTP echo server for local adapter testing."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple

HOST = "127.0.0.1"
PORT = 8787


class EchoHandler(BaseHTTPRequestHandler):
    """Respond to POST requests with a mock completion payload."""

    server_version = "MockHTTPEcho/1.0"

    def log_message(self, format: str, *args: object) -> None:  # noqa: D401 - BaseHTTPRequestHandler signature
        """Silence default logging; output compact messages instead."""

        print(f"[mock-http] {self.address_string()} - {format % args}")

    def _read_json(self) -> Tuple[dict, str]:
        length_header = self.headers.get("Content-Length")
        length = int(length_header or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        return payload, raw

    def _write_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - HTTP method name
        payload, raw = self._read_json()
        prompt = ""
        if isinstance(payload, dict):
            prompt = str(payload.get("prompt", ""))
        response = {"data": {"text": f"[MOCK] {prompt}"}, "echo": raw}
        self._write_json(200, response)


def main() -> None:
    server = HTTPServer((HOST, PORT), EchoHandler)
    print(f"Mock HTTP echo server listening on http://{HOST}:{PORT}/generate")
    print("Send POST JSON payloads such as {'prompt': 'hello'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping mock server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
