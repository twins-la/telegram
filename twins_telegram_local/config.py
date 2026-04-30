"""Configuration for local hosting of the Telegram twin."""

import os

# Database
DB_PATH = os.environ.get("TWIN_DB_PATH", "data/twin.db")

# Server
HOST = os.environ.get("TWIN_HOST", "0.0.0.0")
PORT = int(os.environ.get("TWIN_PORT", "8080"))

# Base URL — how the twin identifies itself externally
BASE_URL = os.environ.get("TWIN_BASE_URL", f"http://localhost:{PORT}")

# Admin Bearer token for service-wide Twin Plane operations.
# Unset = local-dev convenience: admin endpoints accept any bearer.
ADMIN_TOKEN = os.environ.get("TWIN_ADMIN_TOKEN", "")
