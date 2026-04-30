"""Webhook delivery for the Telegram twin.

Real Telegram delivers updates as ``POST <webhook_url>`` with body
``application/json`` containing a serialized Update. If the bot's
webhook is configured with a secret token, Telegram includes
``X-Telegram-Bot-Api-Secret-Token: <token>``.

Reference: https://core.telegram.org/bots/api#setwebhook (retrieved 2026-04-29)
"""

from typing import Optional, Tuple

import requests


WEBHOOK_TIMEOUT_SECONDS = 15


def deliver_update(
    *,
    url: str,
    update: dict,
    secret_token: str = "",
) -> Tuple[bool, Optional[str], Optional[int]]:
    """Deliver an Update payload to the configured webhook URL.

    Returns ``(ok, reason, status_code)``:
        ok = True on 2xx response
        reason = None on success; specific failure description on error
        status_code = HTTP status if a response was received; else None
    """
    headers = {"Content-Type": "application/json"}
    if secret_token:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret_token

    try:
        resp = requests.post(
            url, json=update, headers=headers, timeout=WEBHOOK_TIMEOUT_SECONDS
        )
    except requests.exceptions.Timeout:
        return (False, f"webhook delivery timed out after {WEBHOOK_TIMEOUT_SECONDS}s", None)
    except requests.exceptions.ConnectionError as exc:
        return (False, f"webhook target unreachable: {exc}", None)
    except requests.exceptions.RequestException as exc:
        return (False, f"webhook delivery raised: {exc.__class__.__name__}", None)

    if 200 <= resp.status_code < 300:
        return (True, None, resp.status_code)
    return (False, f"webhook target returned HTTP {resp.status_code}", resp.status_code)
