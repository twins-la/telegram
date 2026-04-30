"""Telegram Bot API surface — getMe, sendMessage, webhook + getUpdates."""

import json


def test_get_me_returns_user_object(client, bot):
    token = bot["token"]
    resp = client.get(f"/bot{token}/getMe")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    user = body["result"]
    assert user["id"] == bot["bot_id"]
    assert user["is_bot"] is True
    assert user["username"] == bot["username"]


def test_get_me_unknown_token_returns_401(client):
    resp = client.get("/bot1234567:bogus/getMe")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error_code"] == 401
    assert body["description"]


def test_send_message_persists_and_returns_message(client, bot):
    token = bot["token"]
    resp = client.post(
        f"/bot{token}/sendMessage",
        json={"chat_id": 7777, "text": "Hello"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    msg = body["result"]
    assert msg["text"] == "Hello"
    assert msg["chat"]["id"] == 7777
    assert msg["message_id"] >= 1


def test_send_message_missing_text_returns_400(client, bot):
    token = bot["token"]
    resp = client.post(f"/bot{token}/sendMessage", json={"chat_id": 1, "text": ""})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error_code"] == 400
    assert "empty" in body["description"]


def test_send_message_string_chat_id_rejected(client, bot):
    token = bot["token"]
    resp = client.post(
        f"/bot{token}/sendMessage", json={"chat_id": "@somechan", "text": "hi"}
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_unknown_method_returns_404(client, bot):
    token = bot["token"]
    resp = client.post(f"/bot{token}/sendPhoto", json={})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error_code"] == 404
    assert "not found" in body["description"].lower()


def test_set_get_delete_webhook(client, bot):
    token = bot["token"]
    info = client.get(f"/bot{token}/getWebhookInfo").get_json()
    assert info["result"]["url"] == ""

    resp = client.post(
        f"/bot{token}/setWebhook",
        json={"url": "http://example.invalid/cb", "secret_token": "s"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["result"] is True

    info = client.get(f"/bot{token}/getWebhookInfo").get_json()
    assert info["result"]["url"] == "http://example.invalid/cb"

    resp = client.post(f"/bot{token}/deleteWebhook")
    assert resp.status_code == 200
    info = client.get(f"/bot{token}/getWebhookInfo").get_json()
    assert info["result"]["url"] == ""


def test_get_updates_when_webhook_active_returns_409(client, bot):
    token = bot["token"]
    client.post(
        f"/bot{token}/setWebhook", json={"url": "http://example.invalid/cb"}
    )
    resp = client.get(f"/bot{token}/getUpdates")
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error_code"] == 409


def test_set_webhook_form_body_accepted(client, bot):
    """Real Telegram accepts form-encoded params; the twin must too."""
    token = bot["token"]
    resp = client.post(
        f"/bot{token}/setWebhook",
        data={"url": "http://example.invalid/cb"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_set_webhook_allowed_updates_json_string(client, bot):
    """Telegram accepts allowed_updates as a JSON-serialised string in form bodies."""
    token = bot["token"]
    resp = client.post(
        f"/bot{token}/setWebhook",
        data={
            "url": "http://example.invalid/cb",
            "allowed_updates": json.dumps(["message", "edited_message"]),
        },
    )
    assert resp.status_code == 200
    info = client.get(f"/bot{token}/getWebhookInfo").get_json()
    assert info["result"]["allowed_updates"] == ["message", "edited_message"]
