"""Verify every emitted log record satisfies twins-la/LOGGING.md §3.2."""

REQUIRED_FIELDS = {
    "timestamp",
    "twin",
    "tenant_id",
    "correlation_id",
    "plane",
    "operation",
    "resource",
    "outcome",
    "reason",
    "details",
}

VALID_PLANES = {"twin", "control", "data", "runtime"}
VALID_OUTCOMES = {"success", "failure"}


def _drive_traffic(client, bot, tenant_headers):
    token = bot["token"]
    client.get(f"/bot{token}/getMe")
    client.post(f"/bot{token}/sendMessage", json={"chat_id": 1, "text": "hi"})
    # Deliberate failure-path call so the conformance check exercises the
    # outcome="failure"/reason branch (review finding T1).
    client.post(f"/bot{token}/sendMessage", json={"chat_id": 1, "text": ""})
    client.post(f"/bot{token}/setWebhook", json={"url": "http://example.invalid/cb"})
    client.get(f"/bot{token}/getWebhookInfo")
    client.post(f"/bot{token}/deleteWebhook")
    client.post(
        "/_twin/simulate/inbound",
        json={"bot_id": bot["bot_id"], "from_user_id": 1, "text": "yo"},
        headers=tenant_headers,
    )


def test_every_log_record_has_required_fields(client, bot, tenant_headers):
    _drive_traffic(client, bot, tenant_headers)

    resp = client.get("/_twin/logs", headers=tenant_headers)
    assert resp.status_code == 200
    logs = resp.get_json()["logs"]
    assert len(logs) >= 5
    # At least one failure record so the failure-branch assertions execute.
    assert any(r["outcome"] == "failure" for r in logs)

    for record in logs:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"missing required fields {missing} in {record}"
        assert record["twin"] == "telegram"
        assert isinstance(record["tenant_id"], str) and record["tenant_id"]
        assert record["plane"] in VALID_PLANES
        assert record["outcome"] in VALID_OUTCOMES
        # operation is dotted, lowercase
        assert record["operation"]
        assert record["operation"] == record["operation"].lower()
        assert "." in record["operation"]
        # resource is object-or-null
        assert record["resource"] is None or isinstance(record["resource"], dict)
        # details is always present (possibly empty)
        assert isinstance(record["details"], dict)
        # timestamp is RFC 3339 UTC with Z suffix
        assert record["timestamp"].endswith("Z")
        # for failures, reason is a non-empty string
        if record["outcome"] == "failure":
            assert isinstance(record["reason"], str) and record["reason"]
