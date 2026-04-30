"""Admin auth + tenant isolation on /_twin/logs."""

import base64

from twins_local.tenants import (
    generate_tenant_id,
    generate_tenant_secret,
    hash_secret,
)


def _basic(tenant_id: str, secret: str) -> dict:
    creds = base64.b64encode(f"{tenant_id}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def test_logs_are_isolated_per_tenant(client, tenant_store):
    # Two tenants, each creates a bot to generate log activity.
    a_id, a_secret = generate_tenant_id(), generate_tenant_secret()
    b_id, b_secret = generate_tenant_id(), generate_tenant_secret()
    tenant_store.create_tenant(tenant_id=a_id, secret_hash=hash_secret(a_secret), friendly_name="A")
    tenant_store.create_tenant(tenant_id=b_id, secret_hash=hash_secret(b_secret), friendly_name="B")

    a_h = _basic(a_id, a_secret)
    b_h = _basic(b_id, b_secret)

    client.post("/_twin/accounts", json={"username": "a"}, headers=a_h)
    client.post("/_twin/accounts", json={"username": "b"}, headers=b_h)

    a_logs = client.get("/_twin/logs", headers=a_h).get_json()["logs"]
    b_logs = client.get("/_twin/logs", headers=b_h).get_json()["logs"]

    assert all(r["tenant_id"] == a_id for r in a_logs)
    assert all(r["tenant_id"] == b_id for r in b_logs)
    # Neither set leaks into the other.
    assert not any(r["tenant_id"] == b_id for r in a_logs)
    assert not any(r["tenant_id"] == a_id for r in b_logs)


def test_admin_bearer_sees_all_logs(client, tenant_headers, twin_app):
    # local-dev: no admin token configured → any bearer accepted.
    client.post("/_twin/accounts", json={"username": "x"}, headers=tenant_headers)

    admin = client.get(
        "/_twin/logs",
        headers={"Authorization": "Bearer anything"},
    )
    assert admin.status_code == 200
    logs = admin.get_json()["logs"]
    # admin sees logs across tenants — at least the one we just made
    assert len(logs) >= 1


def test_admin_bearer_required_when_token_set(client, twin_app, tenant_headers):
    # Set a real admin token; the empty-bearer fallback should now fail.
    twin_app.config["TWIN_ADMIN_TOKEN"] = "supersecret"

    bad = client.get(
        "/_twin/logs",
        headers={"Authorization": "Bearer wrong"},
    )
    assert bad.status_code == 401

    good = client.get(
        "/_twin/logs",
        headers={"Authorization": "Bearer supersecret"},
    )
    assert good.status_code == 200
