"""ID and token generation for the Telegram twin.

Telegram Bot tokens follow the format ``<bot_id>:<secret>`` where
``bot_id`` is an integer and ``secret`` is a 35-character URL-safe
random string (per the actual Bot API token shape).

Other identifiers (update_id, message_id) are integers managed by
storage as monotonically increasing sequences scoped to their parent
resource.
"""

import secrets


_BOT_ID_MIN = 10**8
_BOT_ID_MAX = 10**12


def generate_bot_id() -> int:
    """Generate a random integer bot id in Telegram's typical range."""
    return secrets.randbelow(_BOT_ID_MAX - _BOT_ID_MIN) + _BOT_ID_MIN


def generate_bot_token(bot_id: int) -> str:
    """Generate a Telegram-format bot token: ``<bot_id>:<35-char-urlsafe>``."""
    secret = secrets.token_urlsafe(26)[:35]
    return f"{bot_id}:{secret}"


def generate_feedback_id() -> str:
    """Generate a feedback id (twin-internal — not Telegram-shaped)."""
    return "FB" + secrets.token_hex(16)
