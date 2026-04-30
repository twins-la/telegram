"""DTO/JSON shapes for Telegram Bot API objects.

Reference: https://core.telegram.org/bots/api (retrieved 2026-04-29).

The twin only emits the fields required by the supported messaging
scenario. Out-of-scope fields are omitted rather than fabricated; real
SDKs treat absent optional fields as None.
"""

from datetime import datetime, timezone


def now_unix() -> int:
    """Current time as a unix timestamp (Telegram uses int seconds)."""
    return int(datetime.now(tz=timezone.utc).timestamp())


def bot_to_user_json(bot: dict) -> dict:
    """Render a stored bot as a Telegram ``User`` object (the bot's own identity).

    Used by ``getMe``. Telegram's User-for-bot has ``is_bot=True`` and
    ``can_join_groups`` / ``can_read_all_group_messages`` /
    ``supports_inline_queries`` flags. We default these to safe values
    (joinable, not reading all messages, no inline) — they are out of
    scope for the messaging scenario.
    """
    return {
        "id": bot["id"],
        "is_bot": True,
        "first_name": bot.get("first_name", "") or bot.get("username", ""),
        "username": bot.get("username", ""),
        "can_join_groups": True,
        "can_read_all_group_messages": False,
        "supports_inline_queries": False,
    }


def user_json(user_id: int, *, is_bot: bool = False, first_name: str = "User", username: str = "") -> dict:
    """Build a Telegram ``User`` object."""
    out = {
        "id": user_id,
        "is_bot": is_bot,
        "first_name": first_name,
    }
    if username:
        out["username"] = username
    return out


def chat_json(chat_id: int, chat_type: str = "private", **extra) -> dict:
    """Build a Telegram ``Chat`` object."""
    out = {"id": chat_id, "type": chat_type}
    out.update(extra)
    return out


def message_to_json(msg: dict) -> dict:
    """Render a stored message as a Telegram ``Message`` object."""
    out = {
        "message_id": msg["message_id"],
        "date": msg.get("date") or now_unix(),
        "chat": msg["chat"],
        "text": msg.get("text", ""),
    }
    if msg.get("from"):
        out["from"] = msg["from"]
    return out


def update_json(update_id: int, message: dict) -> dict:
    """Render a stored update as a Telegram ``Update`` object."""
    return {"update_id": update_id, "message": message}


def webhook_info_json(webhook: dict | None) -> dict:
    """Render a stored webhook record as a Telegram ``WebhookInfo`` object.

    When no webhook is set, ``url`` is the empty string per real Telegram.
    """
    if not webhook:
        return {
            "url": "",
            "has_custom_certificate": False,
            "pending_update_count": 0,
        }
    out = {
        "url": webhook.get("url", ""),
        "has_custom_certificate": False,
        "pending_update_count": webhook.get("pending_update_count", 0),
    }
    if webhook.get("allowed_updates"):
        out["allowed_updates"] = webhook["allowed_updates"]
    return out
