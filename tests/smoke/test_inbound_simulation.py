"""Twin Plane: POST /_twin/simulate/inbound.

Two paths:
  - No webhook configured → Update is queued for getUpdates.
  - Webhook configured → Update is delivered via HTTP POST. We stub
    the HTTP layer with a fake server (werkzeug + threading).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _CapturingHandler(BaseHTTPRequestHandler):
    captured = []

    def do_POST(self):  # noqa: N802 — stdlib API
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        _CapturingHandler.captured.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args, **_kwargs):  # silence
        return


def _start_capture_server():
    _CapturingHandler.captured = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_inbound_without_webhook_queues_update(client, bot, tenant_headers):
    resp = client.post(
        "/_twin/simulate/inbound",
        json={"bot_id": bot["bot_id"], "from_user_id": 42, "text": "ping"},
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["webhook"]["webhook_delivered"] is False
    assert body["update"]["update_id"] == 1
    assert body["update"]["message"]["text"] == "ping"

    # getUpdates returns it
    token = bot["token"]
    updates = client.get(f"/bot{token}/getUpdates").get_json()["result"]
    assert len(updates) == 1
    assert updates[0]["message"]["text"] == "ping"


def test_inbound_with_webhook_delivers_to_url(client, bot, tenant_headers):
    server, _thread = _start_capture_server()
    try:
        port = server.server_address[1]
        token = bot["token"]
        url = f"http://127.0.0.1:{port}/cb"

        client.post(
            f"/bot{token}/setWebhook",
            json={"url": url, "secret_token": "topsecret"},
        )

        resp = client.post(
            "/_twin/simulate/inbound",
            json={
                "bot_id": bot["bot_id"],
                "from_user_id": 99,
                "text": "ahoy",
            },
            headers=tenant_headers,
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["webhook"]["webhook_delivered"] is True
        assert body["webhook"]["status_code"] == 200
    finally:
        server.shutdown()
        server.server_close()

    captured = _CapturingHandler.captured
    assert len(captured) == 1
    assert captured[0]["path"] == "/cb"
    assert captured[0]["headers"].get("X-Telegram-Bot-Api-Secret-Token") == "topsecret"
    payload = json.loads(captured[0]["body"])
    assert payload["update_id"] == 1
    assert payload["message"]["text"] == "ahoy"


def test_inbound_unknown_bot_404(client, bot, tenant_headers):
    resp = client.post(
        "/_twin/simulate/inbound",
        json={"bot_id": 999999, "from_user_id": 1, "text": "x"},
        headers=tenant_headers,
    )
    assert resp.status_code == 404
