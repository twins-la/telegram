"""Shared fixtures for the Telegram twin smoke tests.

Starts the twin in-process using Flask's test client, SQLite storage,
and an in-process SQLiteTenantStore. No Docker or external process is
needed for testing.
"""

import base64
import os
import sys

import pytest

from twins_telegram.app import create_app

# twins_telegram_local sibling lives inside this repo; put repo root on sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from twins_telegram_local.storage_sqlite import SQLiteStorage  # noqa: E402
from twins_local.tenants import (  # noqa: E402
    SQLiteTenantStore,
    ensure_default_tenant,
    generate_tenant_id,
    generate_tenant_secret,
    hash_secret,
)


@pytest.fixture
def tenant_store(tmp_path):
    store = SQLiteTenantStore(db_path=str(tmp_path / "tenants.sqlite3"))
    ensure_default_tenant(store)
    return store


@pytest.fixture
def twin_app(tmp_path, tenant_store):
    storage = SQLiteStorage(db_path=str(tmp_path / "test_twin.db"))
    app = create_app(
        storage=storage,
        tenants=tenant_store,
        config={"base_url": "http://localhost:8080"},
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(twin_app):
    return twin_app.test_client()


@pytest.fixture
def tenant(tenant_store):
    tenant_id = generate_tenant_id()
    tenant_secret = generate_tenant_secret()
    tenant_store.create_tenant(
        tenant_id=tenant_id,
        secret_hash=hash_secret(tenant_secret),
        friendly_name="Test Tenant",
    )
    return {"tenant_id": tenant_id, "tenant_secret": tenant_secret}


@pytest.fixture
def tenant_headers(tenant):
    creds = base64.b64encode(
        f"{tenant['tenant_id']}:{tenant['tenant_secret']}".encode()
    ).decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture
def bot(client, tenant_headers):
    """Create and return a bot inside the test tenant."""
    resp = client.post(
        "/_twin/accounts",
        json={"username": "test_bot", "first_name": "Test Bot"},
        headers=tenant_headers,
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()
