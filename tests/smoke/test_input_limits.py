"""Resource-bound guards across the bot API and twin-plane (security).

Covers TWTG-003: limit clamps (list_logs, getUpdates), feedback pagination,
text-length caps (sendMessage, simulate/inbound), and MAX_CONTENT_LENGTH.
"""


def test_list_logs_limit_is_clamped(client, tenant_headers):
    resp = client.get("/_twin/logs?limit=10000000", headers=tenant_headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["limit"] == 1000


def test_list_logs_negative_limit_floored(client, tenant_headers):
    resp = client.get("/_twin/logs?limit=-1", headers=tenant_headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["limit"] == 1


def test_list_feedback_is_paginated(client, tenant_headers):
    resp = client.get("/_twin/feedback?limit=10000000", headers=tenant_headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["limit"] == 1000
    assert body["offset"] == 0


def test_get_updates_limit_is_clamped(client, bot, tenant_headers):
    # Seed >100 pending updates, then ask for far more than Telegram's max.
    for i in range(105):
        client.post(
            "/_twin/simulate/inbound",
            json={"bot_id": bot["bot_id"], "from_user_id": 42, "text": f"m{i}"},
            headers=tenant_headers,
        )
    token = bot["token"]
    result = client.get(f"/bot{token}/getUpdates?limit=100000").get_json()["result"]
    assert len(result) == 100  # clamped to the real-API maximum, not 105


def test_send_message_text_length_capped(client, bot):
    token = bot["token"]
    resp = client.post(
        f"/bot{token}/sendMessage",
        json={"chat_id": 7777, "text": "x" * 4097},
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_simulate_inbound_text_length_capped(client, bot, tenant_headers):
    resp = client.post(
        "/_twin/simulate/inbound",
        json={"bot_id": bot["bot_id"], "from_user_id": 42, "text": "x" * 4097},
        headers=tenant_headers,
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_oversize_request_body_rejected(client, bot):
    token = bot["token"]
    big = "x" * (1 * 1024 * 1024 + 1)
    resp = client.post(
        f"/bot{token}/sendMessage",
        data='{"chat_id": 1, "text": "' + big + '"}',
        content_type="application/json",
    )
    assert resp.status_code == 413, resp.get_data(as_text=True)
