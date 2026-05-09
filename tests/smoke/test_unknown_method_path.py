"""Sweep test: unknown ``/bot<token>/<method>`` paths return
Telegram-shaped JSON 404. Closes twins-la/twins-la#2 (telegram half).

The catch-all already lives in `routes/bot_api.py:unknown_method`; this
sweep is the explicit coverage that asserts the envelope shape and
ensures no HTML leaks from any method/path combination.

Telegram's documented error envelope is
``{ok: false, error_code: <int>, description: <str>}``.
"""

import pytest


@pytest.mark.parametrize(
    "method,path_method",
    [
        ("GET", "sendPhoto"),
        ("POST", "sendVideo"),
        ("GET", "deleteMessage"),
        ("POST", "editMessageText"),
        ("GET", "getChatMember"),
        ("POST", "answerInlineQuery"),
        ("GET", "stopPoll"),
    ],
)
def test_unknown_bot_api_method_returns_json_404(client, bot, method, path_method):
    token = bot["token"]
    full = f"/bot{token}/{path_method}"
    resp = client.open(
        full,
        method=method,
        json={"foo": "bar"} if method == "POST" else None,
    )
    assert resp.status_code == 404, f"{method} {full} got {resp.status_code}"
    assert resp.headers["Content-Type"].startswith("application/json"), (
        f"{method} {full} returned {resp.headers.get('Content-Type')!r} "
        f"body={resp.get_data(as_text=True)[:200]!r}"
    )
    body = resp.get_json()
    assert body is not None
    # Telegram envelope: {ok: false, error_code: <int>, description: <str>}.
    assert body["ok"] is False
    assert body["error_code"] == 404
    assert "not found" in body["description"].lower()


def test_unknown_bot_api_method_no_html_leak(client, bot):
    token = bot["token"]
    resp = client.get(f"/bot{token}/literally-anything")
    body = resp.get_data(as_text=True)
    assert "<!doctype" not in body.lower()
