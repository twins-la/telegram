"""Telegram Bot API surface — emulates ``https://api.telegram.org/bot<token>/<METHOD>``.

Supported methods (Scenario: messaging):
  getMe, sendMessage, getUpdates, setWebhook, deleteWebhook, getWebhookInfo

Out-of-scope methods return Telegram's 404 response shape.

References:
  - https://core.telegram.org/bots/api (retrieved 2026-04-29)
  - https://core.telegram.org/bots/webhooks (retrieved 2026-04-29)
"""

import logging

from flask import Blueprint, g, jsonify, request

from ..auth import require_bot_token
from ..errors import bad_request, conflict, not_found, unauthorized
from ..logs import emit
from ..models import (
    bot_to_user_json,
    chat_json,
    message_to_json,
    now_unix,
    user_json,
    webhook_info_json,
)

logger = logging.getLogger(__name__)

bot_api_bp = Blueprint("bot_api", __name__, url_prefix="/bot<token>")


def _ok(result):
    return jsonify({"ok": True, "result": result})


def _params() -> dict:
    """Read params from JSON body, form body, or query string — Telegram accepts all three."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return request.form.to_dict()
    return request.args.to_dict()


# ---- /getMe ----


@bot_api_bp.route("/getMe", methods=["GET", "POST"])
@require_bot_token
def get_me(token):
    """Return the bot's own User object."""
    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.bot.fetch",
        resource={"type": "bot", "id": str(g.bot["id"])},
    )
    return _ok(bot_to_user_json(g.bot))


# ---- /sendMessage ----


@bot_api_bp.route("/sendMessage", methods=["GET", "POST"])
@require_bot_token
def send_message(token):
    """Send a text message from the bot to a chat.

    Required params: chat_id (int), text (non-empty str).
    """
    params = _params()
    chat_id_raw = params.get("chat_id")
    text = params.get("text", "")

    if chat_id_raw is None or chat_id_raw == "":
        emit(
            g.storage,
            tenant_id=g.bot["tenant_id"],
            plane="data",
            operation="data.message.send",
            outcome="failure",
            reason="chat_id parameter is missing",
        )
        return bad_request("chat_id is required")

    try:
        chat_id = int(chat_id_raw)
    except (TypeError, ValueError):
        emit(
            g.storage,
            tenant_id=g.bot["tenant_id"],
            plane="data",
            operation="data.message.send",
            outcome="failure",
            reason="chat_id is not an integer (string @username chat_ids are out of scope for the messaging scenario)",
        )
        return bad_request("chat_id must be an integer")

    if not text or not str(text).strip():
        emit(
            g.storage,
            tenant_id=g.bot["tenant_id"],
            plane="data",
            operation="data.message.send",
            outcome="failure",
            reason="message text is empty",
        )
        return bad_request("message text is empty")

    msg = g.storage.create_message(
        {
            "bot_id": g.bot["id"],
            "tenant_id": g.bot["tenant_id"],
            "chat_id": chat_id,
            "from": bot_to_user_json(g.bot),
            "chat": chat_json(chat_id),
            "text": str(text),
            "direction": "outbound",
            "date": now_unix(),
        }
    )

    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.message.send",
        resource={"type": "message", "id": str(msg["message_id"])},
        details={"bot_id": g.bot["id"], "chat_id": chat_id, "text": str(text)},
    )

    return _ok(message_to_json(msg))


# ---- /getUpdates ----


@bot_api_bp.route("/getUpdates", methods=["GET", "POST"])
@require_bot_token
def get_updates(token):
    """Return queued Updates for this bot.

    The twin returns immediately with whatever is queued; long-polling
    fidelity (the ``timeout`` param) is intentionally out of scope
    (SCENARIOS.md). ``offset`` semantics are honoured — supplying offset=N
    acks updates with update_id < N.
    """
    if g.storage.get_webhook(g.bot["id"]):
        return conflict(
            "can't use getUpdates method while webhook is active; use deleteWebhook to remove it"
        )

    params = _params()
    try:
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 100))
    except (TypeError, ValueError):
        return bad_request("offset and limit must be integers")

    updates = g.storage.get_pending_updates(g.bot["id"], offset=offset, limit=limit)
    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.update.poll",
        details={"bot_id": g.bot["id"], "offset": offset, "returned": len(updates)},
    )
    return _ok(updates)


# ---- /setWebhook ----


@bot_api_bp.route("/setWebhook", methods=["GET", "POST"])
@require_bot_token
def set_webhook(token):
    """Configure (or replace) the webhook URL for this bot."""
    params = _params()
    url = params.get("url", "")
    secret_token = params.get("secret_token", "")

    if not url:
        return bad_request("url is required")
    if not isinstance(url, str):
        return bad_request("url must be a string")

    if g.is_cloud and not url.startswith("https://"):
        emit(
            g.storage,
            tenant_id=g.bot["tenant_id"],
            plane="data",
            operation="data.webhook.set",
            outcome="failure",
            reason="webhook url must use HTTPS in cloud deployments",
            details={"bot_id": g.bot["id"], "url": url},
        )
        return bad_request("HTTPS url must be provided for webhook")

    allowed = params.get("allowed_updates")
    if isinstance(allowed, str):
        # Telegram accepts JSON-serialized arrays in form bodies
        import json as _json

        try:
            allowed = _json.loads(allowed)
        except _json.JSONDecodeError:
            return bad_request("allowed_updates must be a JSON-serialized array")
    if allowed is not None and not isinstance(allowed, list):
        return bad_request("allowed_updates must be an array of strings")

    g.storage.set_webhook(
        bot_id=g.bot["id"],
        url=url,
        secret_token=secret_token,
        allowed_updates=allowed,
    )
    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.webhook.set",
        resource={"type": "webhook", "id": str(g.bot["id"])},
        details={"bot_id": g.bot["id"], "url": url},
    )
    return _ok(True)


# ---- /deleteWebhook ----


@bot_api_bp.route("/deleteWebhook", methods=["GET", "POST"])
@require_bot_token
def delete_webhook(token):
    """Remove the bot's webhook config and (optionally) drop pending updates."""
    params = _params()
    drop = str(params.get("drop_pending_updates", "")).lower() in ("true", "1")

    g.storage.delete_webhook(g.bot["id"], drop_pending_updates=drop)
    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.webhook.delete",
        resource={"type": "webhook", "id": str(g.bot["id"])},
        details={"bot_id": g.bot["id"], "drop_pending_updates": drop},
    )
    return _ok(True)


# ---- /getWebhookInfo ----


@bot_api_bp.route("/getWebhookInfo", methods=["GET", "POST"])
@require_bot_token
def get_webhook_info(token):
    """Return the current ``WebhookInfo`` for the bot."""
    webhook = g.storage.get_webhook(g.bot["id"])
    emit(
        g.storage,
        tenant_id=g.bot["tenant_id"],
        plane="data",
        operation="data.webhook.get",
        details={"bot_id": g.bot["id"]},
    )
    return _ok(webhook_info_json(webhook))


# ---- Catch-all for out-of-scope methods ----


@bot_api_bp.route("/<method>", methods=["GET", "POST"])
def unknown_method(token, method):
    """Return Telegram's 404 shape for unsupported methods.

    Auth happens before method dispatch in real Telegram; we mirror that:
    if the token is unknown, return 401 first; otherwise 404 for the method.
    """
    bot = g.storage.get_bot_by_token(token)
    if not bot:
        return unauthorized()
    emit(
        g.storage,
        tenant_id=bot["tenant_id"],
        plane="data",
        operation="data.method.unknown",
        outcome="failure",
        reason=f"method {method!r} is out of scope for the messaging scenario",
        details={"bot_id": bot["id"], "method": method},
    )
    return not_found(method)
