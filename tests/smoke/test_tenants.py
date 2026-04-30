"""Tenant bootstrap + auth on Twin Plane endpoints."""

import base64


def test_tenant_bootstrap_returns_id_and_secret_once(client):
    resp = client.post("/_twin/tenants", json={"friendly_name": "First"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["tenant_id"]
    assert body["tenant_secret"]
    assert body["friendly_name"] == "First"
    assert body["created_at"]


def test_logs_endpoint_requires_auth(client):
    resp = client.get("/_twin/logs")
    assert resp.status_code == 401


def test_accounts_create_requires_auth(client):
    resp = client.post("/_twin/accounts", json={"username": "x"})
    assert resp.status_code == 401


def test_tenant_can_access_own_resources(client, tenant_headers):
    resp = client.post(
        "/_twin/accounts",
        json={"username": "alpha"},
        headers=tenant_headers,
    )
    assert resp.status_code == 201

    resp = client.get("/_twin/accounts", headers=tenant_headers)
    assert resp.status_code == 200
    accounts = resp.get_json()["accounts"]
    assert len(accounts) == 1
    assert accounts[0]["username"] == "alpha"


def test_wrong_secret_is_rejected(client, tenant):
    bad = base64.b64encode(
        f"{tenant['tenant_id']}:wrong-secret".encode()
    ).decode()
    resp = client.get(
        "/_twin/logs",
        headers={"Authorization": f"Basic {bad}"},
    )
    assert resp.status_code == 401
