"""Telegram Bot API authentication.

Real Telegram authenticates by token-in-URL: every API request goes to
``/bot<token>/<METHOD>``. The twin matches that exactly and rejects:

* unknown tokens with HTTP 401 + ``{ok: false, error_code: 401, description: "Unauthorized"}``.
* malformed paths with HTTP 404 (handled by Flask routing — no match).

This is **provider-API auth only**. Twin Plane endpoints use tenant /
admin auth via ``twins_local.tenants.auth`` decorators.
"""

import functools

from flask import g

from .errors import unauthorized


def require_bot_token(f):
    """Decorator that resolves the URL ``<token>`` to a stored bot.

    Sets ``g.bot`` on success.
    """

    @functools.wraps(f)
    def wrapper(token, *args, **kwargs):
        bot = g.storage.get_bot_by_token(token)
        if not bot:
            return unauthorized()
        g.bot = bot
        return f(token, *args, **kwargs)

    return wrapper
