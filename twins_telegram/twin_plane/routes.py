"""Twin Plane management API for the Telegram twin.

Served at ``/_twin/`` — separate from the Bot API surface.

Authentication:
  - ``POST /_twin/tenants`` (bootstrap — creates credentials) is unauthenticated.
  - ``GET  /_twin/health``, ``/scenarios``, ``/references``, ``/settings`` are unauthenticated read-only.
  - All other endpoints require tenant auth (Basic ``tenant_id:tenant_secret``)
    or operator-admin (Bearer or ``X-Twin-Admin-Token``).

All authenticated endpoints are scoped to the caller's tenant (admin
sees across tenants).
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from twins_local.tenants import (
    OPERATOR_ADMIN_TENANT_ID,
    generate_tenant_id,
    generate_tenant_secret,
    hash_secret,
    reject_default_in_cloud,
)

from .. import __version__
from ..auth import require_bot_token  # noqa: F401  (kept for explicit import surface)
from ..logs import emit
from ..models import (
    bot_to_user_json,
    chat_json,
    message_to_json,
    now_unix,
    update_json,
    user_json,
)
from ..sids import generate_bot_id, generate_bot_token, generate_feedback_id
from ..webhooks import deliver_update
from .auth import require_admin, require_tenant, require_tenant_or_admin

logger = logging.getLogger(__name__)

twin_plane_bp = Blueprint("twin_plane", __name__, url_prefix="/_twin")


def _scope_tenant_id() -> str:
    """tenant_id to stamp on log records for the current request."""
    return OPERATOR_ADMIN_TENANT_ID if g.get("is_admin") else g.tenant_id


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.now(tz=timezone.utc).microsecond // 1000:03d}Z"
    )


# ---- Public info endpoints ----


@twin_plane_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "twin": "telegram", "version": __version__})


@twin_plane_bp.route("/scenarios", methods=["GET"])
def scenarios():
    return jsonify(
        {
            "scenarios": [
                {
                    "name": "messaging",
                    "status": "supported",
                    "description": "Outbound text messages and inbound webhook delivery via the Telegram Bot API",
                    "capabilities": [
                        "bot_identity",
                        "outbound_text_message",
                        "webhook_configuration",
                        "webhook_delivery_with_secret_token",
                        "long_polling_via_get_updates",
                        "inbound_message_simulation",
                    ],
                },
            ],
        }
    )


@twin_plane_bp.route("/references", methods=["GET"])
def references():
    return jsonify(
        {
            "references": [
                {
                    "title": "Telegram Bot API",
                    "url": "https://core.telegram.org/bots/api",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bots — Authentication / Tokens",
                    "url": "https://core.telegram.org/bots#how-do-i-create-a-bot",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bot Webhooks",
                    "url": "https://core.telegram.org/bots/webhooks",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bot API — getMe",
                    "url": "https://core.telegram.org/bots/api#getme",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bot API — sendMessage",
                    "url": "https://core.telegram.org/bots/api#sendmessage",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bot API — Update object",
                    "url": "https://core.telegram.org/bots/api#update",
                    "retrieved": "2026-04-29",
                },
                {
                    "title": "Telegram Bot API — setWebhook",
                    "url": "https://core.telegram.org/bots/api#setwebhook",
                    "retrieved": "2026-04-29",
                },
            ],
        }
    )


@twin_plane_bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify({"twin": "telegram", "version": __version__, "base_url": g.base_url})


# ---- Tenants (bootstrap) ----


@twin_plane_bp.route("/tenants", methods=["POST"])
def create_tenant():
    """Bootstrap a new tenant. Returns ``tenant_id`` and ``tenant_secret`` once."""
    payload = request.get_json(silent=True) or {}
    friendly_name = payload.get("friendly_name", "") if isinstance(payload, dict) else ""

    tenant_id = generate_tenant_id()
    if g.is_cloud:
        reject_default_in_cloud(tenant_id)

    tenant_secret = generate_tenant_secret()
    tenant = g.tenants.create_tenant(
        tenant_id=tenant_id,
        secret_hash=hash_secret(tenant_secret),
        friendly_name=friendly_name,
    )

    emit(
        g.storage,
        tenant_id=tenant_id,
        plane="twin",
        operation="twin.tenant.create",
        resource={"type": "tenant", "id": tenant_id},
    )

    resp = jsonify(
        {
            "tenant_id": tenant_id,
            "tenant_secret": tenant_secret,
            "friendly_name": tenant["friendly_name"],
            "created_at": tenant["created_at"],
        }
    )
    resp.status_code = 201
    return resp


# ---- Logs ----


@twin_plane_bp.route("/logs", methods=["GET"])
@require_tenant_or_admin
def list_logs():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    tenant_id = None if g.is_admin else g.tenant_id
    entries = g.storage.list_logs(limit=limit, offset=offset, tenant_id=tenant_id)
    return jsonify({"logs": entries, "limit": limit, "offset": offset})


# ---- Accounts (= Bots) ----


@twin_plane_bp.route("/accounts", methods=["POST"])
@require_tenant
def create_account():
    """Create a Telegram bot inside the authenticated tenant.

    Real bot creation requires BotFather; the twin makes it a simple API
    call. The token is shown once and cannot be retrieved again.
    """
    payload = request.get_json(silent=True) or {}
    username = payload.get("username") or f"twin_bot_{generate_bot_id() % 100000}"
    first_name = payload.get("first_name", username)

    bot_id = generate_bot_id()
    token = generate_bot_token(bot_id)

    bot = g.storage.create_bot(
        tenant_id=g.tenant_id,
        bot_id=bot_id,
        token=token,
        username=username,
        first_name=first_name,
    )

    emit(
        g.storage,
        tenant_id=g.tenant_id,
        plane="twin",
        operation="twin.account.create",
        resource={"type": "bot", "id": str(bot_id)},
    )

    resp = jsonify(
        {
            "bot_id": bot["id"],
            "token": token,
            "username": bot["username"],
            "first_name": bot["first_name"],
        }
    )
    resp.status_code = 201
    return resp


def _bot_public(bot: dict) -> dict:
    """Public bot view (no token)."""
    return {
        "bot_id": bot["id"],
        "username": bot.get("username", ""),
        "first_name": bot.get("first_name", ""),
        "tenant_id": bot.get("tenant_id", ""),
    }


@twin_plane_bp.route("/accounts", methods=["GET"])
@require_tenant_or_admin
def list_accounts():
    if g.is_admin:
        bots = g.storage.list_bots()
    else:
        bots = g.storage.list_bots(tenant_id=g.tenant_id)
    return jsonify({"accounts": [_bot_public(b) for b in bots]})


# ---- Inbound simulation ----


@twin_plane_bp.route("/simulate/inbound", methods=["POST"])
@require_tenant
def simulate_inbound():
    """Simulate an inbound message addressed to a bot.

    Body:
        bot_id (int, required) — the destination bot in this tenant.
        from_user_id (int, required) — sender user id.
        chat_id (int, optional) — defaults to from_user_id (private chat).
        text (str, required) — message text.
        from_username (str, optional)
        from_first_name (str, optional)

    Behaviour:
        - Persist the inbound message.
        - If a webhook is configured, attempt delivery; record success or
          failure with a specific reason. The HTTP response always returns
          200 with the delivery report — failed delivery is information,
          not an error condition for the simulator.
        - If no webhook, queue the Update for ``getUpdates``.
    """
    payload = request.get_json(silent=True) or {}
    bot_id_raw = payload.get("bot_id")
    text = payload.get("text")
    from_user_id_raw = payload.get("from_user_id")

    if bot_id_raw is None:
        return jsonify({"error": "'bot_id' is required"}), 400
    if from_user_id_raw is None:
        return jsonify({"error": "'from_user_id' is required"}), 400
    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' is required"}), 400

    try:
        bot_id = int(bot_id_raw)
        from_user_id = int(from_user_id_raw)
        chat_id = int(payload.get("chat_id", from_user_id))
    except (TypeError, ValueError):
        return jsonify({"error": "bot_id, from_user_id, and chat_id must be integers"}), 400

    bot = g.storage.get_bot(bot_id)
    if not bot or bot.get("tenant_id") != g.tenant_id:
        return jsonify({"error": "Bot not found"}), 404

    sender = user_json(
        from_user_id,
        first_name=payload.get("from_first_name", "User"),
        username=payload.get("from_username", ""),
    )

    msg = g.storage.create_message(
        {
            "bot_id": bot_id,
            "tenant_id": g.tenant_id,
            "chat_id": chat_id,
            "from": sender,
            "chat": chat_json(chat_id),
            "text": text,
            "direction": "inbound",
            "date": now_unix(),
        }
    )

    update = g.storage.queue_update(bot_id, {"message": message_to_json(msg)})

    emit(
        g.storage,
        tenant_id=g.tenant_id,
        plane="twin",
        operation="twin.simulate.inbound",
        resource={"type": "message", "id": str(msg["message_id"])},
        details={
            "bot_id": bot_id,
            "chat_id": chat_id,
            "from_user_id": from_user_id,
            "text": text,
        },
    )

    webhook = g.storage.get_webhook(bot_id)
    delivery = {"webhook_delivered": False, "webhook_url": "", "reason": None}

    if webhook and webhook.get("url"):
        ok, reason, status_code = deliver_update(
            url=webhook["url"],
            update=update,
            secret_token=webhook.get("secret_token", ""),
        )
        delivery = {
            "webhook_delivered": ok,
            "webhook_url": webhook["url"],
            "reason": reason,
            "status_code": status_code,
        }
        emit(
            g.storage,
            tenant_id=g.tenant_id,
            plane="runtime",
            operation="runtime.message.deliver",
            resource={"type": "message", "id": str(msg["message_id"])},
            outcome="success" if ok else "failure",
            reason=reason,
            details={"bot_id": bot_id, "url": webhook["url"], "status_code": status_code},
        )

    return jsonify(
        {
            "update": update,
            "message": message_to_json(msg),
            "webhook": delivery,
        }
    ), 201


# ---- Feedback ----


@twin_plane_bp.route("/feedback", methods=["POST"])
@require_tenant
def submit_feedback():
    payload = request.get_json(silent=True) or {}
    body = payload.get("body")
    if not body or not isinstance(body, str) or not body.strip():
        return jsonify({"error": "'body' is required"}), 400

    feedback_id = generate_feedback_id()
    now = _now_iso()
    record = g.storage.create_feedback(
        {
            "id": feedback_id,
            "tenant_id": g.tenant_id,
            "body": body.strip(),
            "category": payload.get("category", ""),
            "context": payload.get("context", {}),
            "status": "pending",
            "date_created": now,
            "date_updated": now,
        }
    )
    emit(
        g.storage,
        tenant_id=g.tenant_id,
        plane="twin",
        operation="twin.feedback.submit",
        resource={"type": "feedback", "id": feedback_id},
        details={"category": record["category"]},
    )
    return jsonify(record), 201


@twin_plane_bp.route("/feedback", methods=["GET"])
@require_tenant_or_admin
def list_feedback():
    status = request.args.get("status")
    tenant_id = None if g.is_admin else g.tenant_id
    items = g.storage.list_feedback(status=status, tenant_id=tenant_id)
    return jsonify({"feedback": items})


@twin_plane_bp.route("/feedback/<feedback_id>", methods=["GET"])
@require_tenant_or_admin
def get_feedback(feedback_id):
    record = g.storage.get_feedback(feedback_id)
    if not record:
        return jsonify({"error": "Feedback not found"}), 404
    if not g.is_admin and record.get("tenant_id") != g.tenant_id:
        return jsonify({"error": "Feedback not found"}), 404
    return jsonify(record)


@twin_plane_bp.route("/feedback/<feedback_id>", methods=["POST"])
@require_tenant_or_admin
def update_feedback(feedback_id):
    record = g.storage.get_feedback(feedback_id)
    if not record:
        return jsonify({"error": "Feedback not found"}), 404
    if not g.is_admin and record.get("tenant_id") != g.tenant_id:
        return jsonify({"error": "Feedback not found"}), 404

    payload = request.get_json(silent=True) or {}
    updates = {}
    if "status" in payload:
        updates["status"] = payload["status"]
    updates["date_updated"] = _now_iso()
    record = g.storage.update_feedback(feedback_id, updates)

    emit(
        g.storage,
        tenant_id=_scope_tenant_id(),
        plane="twin",
        operation="twin.feedback.update",
        resource={"type": "feedback", "id": feedback_id},
        details={"status": updates.get("status", "")},
    )
    return jsonify(record)
