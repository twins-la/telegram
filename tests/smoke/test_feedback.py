"""Twin Plane feedback endpoints."""


def test_feedback_submit_and_list(client, tenant_headers):
    resp = client.post(
        "/_twin/feedback",
        json={
            "body": "sendMessage didn't echo entities back",
            "category": "bug",
            "context": {"method": "sendMessage"},
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    fb = resp.get_json()
    assert fb["id"]
    assert fb["status"] == "pending"
    assert fb["category"] == "bug"

    listing = client.get("/_twin/feedback", headers=tenant_headers).get_json()
    assert any(item["id"] == fb["id"] for item in listing["feedback"])


def test_feedback_requires_body(client, tenant_headers):
    resp = client.post("/_twin/feedback", json={}, headers=tenant_headers)
    assert resp.status_code == 400


def test_feedback_unauth_rejected(client):
    resp = client.post("/_twin/feedback", json={"body": "x"})
    assert resp.status_code == 401


def test_feedback_update_status_via_admin(client, tenant_headers):
    resp = client.post(
        "/_twin/feedback",
        json={"body": "x"},
        headers=tenant_headers,
    )
    fb_id = resp.get_json()["id"]

    upd = client.post(
        f"/_twin/feedback/{fb_id}",
        json={"status": "reviewed"},
        headers={"Authorization": "Bearer admin"},
    )
    assert upd.status_code == 200
    assert upd.get_json()["status"] == "reviewed"
