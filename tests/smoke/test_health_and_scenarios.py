"""Twin Plane info endpoints — health, scenarios, references, settings.

References match SCENARIOS.md (Principle 12 + 13: source-grounded and
self-documenting).
"""


def test_health(client):
    resp = client.get("/_twin/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["twin"] == "telegram"
    assert "version" in body


def test_scenarios(client):
    resp = client.get("/_twin/scenarios")
    assert resp.status_code == 200
    scenarios = resp.get_json()["scenarios"]
    names = [s["name"] for s in scenarios]
    assert "messaging" in names
    messaging = next(s for s in scenarios if s["name"] == "messaging")
    assert messaging["status"] == "supported"
    assert "outbound_text_message" in messaging["capabilities"]
    assert "webhook_configuration" in messaging["capabilities"]


def test_references_present_and_dated(client):
    resp = client.get("/_twin/references")
    assert resp.status_code == 200
    refs = resp.get_json()["references"]
    assert len(refs) >= 1
    for r in refs:
        assert r["title"]
        assert r["url"].startswith("https://")
        assert r["retrieved"]


def test_settings(client):
    resp = client.get("/_twin/settings")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["twin"] == "telegram"
    assert "version" in body
    assert "base_url" in body


def test_explainer_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "telegram" in body.lower()
    assert "twins.la" in body


def test_explainer_has_no_html_entities_inside_css_content(client):
    """Sweep-style class check: catches any HTML entity inside a CSS
    content: declaration in the served explainer. Job 021 introduced the
    assertion inline; Job 022 moved the implementation into
    twins_local.testing so every twin uses the same regex.
    """
    from twins_local.testing import assert_no_html_entity_in_css_content

    assert_no_html_entity_in_css_content(client.get("/").get_data(as_text=True))


def test_agent_instructions(client):
    resp = client.get("/_twin/agent-instructions")
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    body = resp.get_data(as_text=True)
    assert "Bot API" in body
    assert "/_twin/tenants" in body
