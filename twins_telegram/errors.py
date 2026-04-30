"""Telegram Bot API error response shapes.

Real Telegram errors are JSON objects:
    {"ok": false, "error_code": <int>, "description": <str>}

The twin must match this shape exactly within supported scenarios so
client SDKs (e.g. python-telegram-bot) parse them as real errors.
"""

from flask import jsonify


def bot_api_error(error_code: int, description: str):
    """Build a Telegram-shape error response with HTTP status set to ``error_code``.

    The HTTP status mirrors ``error_code`` (real Telegram returns the same
    integer in both places for the codes we care about: 400, 401, 404, 409).
    """
    resp = jsonify({"ok": False, "error_code": error_code, "description": description})
    resp.status_code = error_code
    return resp


def unauthorized():
    return bot_api_error(401, "Unauthorized")


def not_found(method: str):
    return bot_api_error(404, f"Not Found: method {method!r} not found")


def bad_request(reason: str):
    return bot_api_error(400, f"Bad Request: {reason}")


def conflict(reason: str):
    return bot_api_error(409, f"Conflict: {reason}")
