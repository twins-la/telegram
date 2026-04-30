"""Flask application factory for the Telegram twin.

The host calls :func:`create_app` with a storage backend, a tenant
store, and configuration, and receives a configured Flask application
to serve. The same factory runs in local (SQLite) and cloud (Postgres)
hosts; behaviour differences come from the injected dependencies, never
from twin code branching on host type.
"""

import logging

from flask import Flask, g

from twins_local.logs import install_correlation_id

from .explainer import explainer_bp
from .routes.bot_api import bot_api_bp
from .storage import TwinStorage
from .twin_plane.routes import twin_plane_bp

logger = logging.getLogger(__name__)


def create_app(
    storage: TwinStorage,
    tenants=None,
    config: dict | None = None,
) -> Flask:
    """Create and configure the Telegram twin Flask application.

    Args:
        storage: A :class:`TwinStorage` implementation provided by the host.
        tenants: A ``TenantStore`` implementation provided by the host.
            Required for Twin Plane tenant auth; tests may omit if they
            do not exercise tenant-protected routes.
        config: Configuration dict. Supported keys:
            - ``base_url`` (str): public-facing URL of the twin
            - ``admin_token`` (str): operator-admin Bearer token
            - ``is_cloud`` (bool): when True, the cloud guard rejects
              ``tenant_id="default"`` and webhook URLs MUST be HTTPS.

    Returns:
        Configured Flask application ready to serve.
    """
    config = config or {}
    base_url = config.get("base_url", "http://localhost:8080")
    admin_token = config.get("admin_token", "")
    is_cloud = bool(config.get("is_cloud", False))

    app = Flask(__name__)
    app.config["TWIN_STORAGE"] = storage
    app.config["TWIN_TENANTS"] = tenants
    app.config["TWIN_BASE_URL"] = base_url
    app.config["TWIN_ADMIN_TOKEN"] = admin_token
    app.config["TWIN_IS_CLOUD"] = is_cloud

    # Stamp every request with a correlation_id so emitted log records
    # share it (twins-la/LOGGING.md §1.2, §3.2).
    install_correlation_id(app)

    @app.before_request
    def inject_context():
        g.storage = app.config["TWIN_STORAGE"]
        g.tenants = app.config["TWIN_TENANTS"]
        g.base_url = app.config["TWIN_BASE_URL"]
        g.admin_token = app.config["TWIN_ADMIN_TOKEN"]
        g.is_cloud = app.config["TWIN_IS_CLOUD"]

    app.register_blueprint(bot_api_bp)
    app.register_blueprint(twin_plane_bp)
    app.register_blueprint(explainer_bp)

    logger.info("Telegram twin created — base_url=%s cloud=%s", base_url, is_cloud)
    return app
