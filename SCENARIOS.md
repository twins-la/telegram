# Telegram Twin — Supported Scenarios

## Messaging (Supported)

The Messaging scenario enables sending and receiving Telegram Bot messages through a Telegram Bot API-compatible HTTP interface. Code written against this twin for the messaging scenario should work against the real `api.telegram.org` with only hostname and credential changes.

### Scope

**In scope:**
- Bot identity: `GET/POST /bot<token>/getMe` returning a Telegram-shape `User` object with `is_bot=true`.
- Outbound text: `POST /bot<token>/sendMessage` with `chat_id` (integer) and `text` parameters; returns a Telegram-shape `Message` object.
- Update polling: `GET/POST /bot<token>/getUpdates` returning queued `Update` objects (with `offset` semantics; `timeout` accepted but ignored — twin returns immediately).
- Webhook configuration: `setWebhook` (with `url`, `secret_token`, `allowed_updates`), `deleteWebhook` (with `drop_pending_updates`), `getWebhookInfo`.
- Webhook delivery: when a webhook is configured, simulated inbound messages POST a JSON-serialised `Update` to the webhook URL with `Content-Type: application/json` and `X-Telegram-Bot-Api-Secret-Token` when set.
- Token-in-URL authentication: every API call goes through `/bot<token>/<method>`. Unknown tokens return Telegram's 401 / "Unauthorized" shape; unknown methods return Telegram's 404 / "Not Found" shape.
- Mutually-exclusive webhook vs polling: with a webhook set, `getUpdates` returns Telegram's 409 / "Conflict" shape.
- Telegram error shape: `{"ok": false, "error_code": <int>, "description": <str>}` on every failure path.
- Inbound message simulation via Twin Plane: `POST /_twin/simulate/inbound` synthesises an `Update` for a bot and either delivers to the configured webhook or queues it for `getUpdates`.

**Out of scope (behaviour may be fabricated):**
- Media: `sendPhoto`, `sendDocument`, `sendVideo`, `sendAudio`, `sendVoice`, `sendAnimation`, `sendVideoNote`, `sendMediaGroup`.
- Files: `getFile`, file uploads, attachments.
- Inline keyboards, `callback_query`, inline mode, `answerInlineQuery`.
- Message edits and deletes: `editMessageText`, `deleteMessage`, etc.
- Polls, dice, games, payments, passports.
- Chat administration: `banChatMember`, `setChatTitle`, `restrictChatMember`, etc.
- Forum topics, threads, reactions.
- `chat_id` as `@username` strings (only integer `chat_id` is in scope).
- `getUpdates` long-polling fidelity (`timeout` is accepted but the twin returns immediately).
- Real network rate limits, retry semantics, or `parameters.retry_after`.
- MTProto client API (this twin is bot-only).

### Authoritative References

- Telegram Bot API: https://core.telegram.org/bots/api (retrieved 2026-04-29)
- Telegram Bots — Authentication / Tokens: https://core.telegram.org/bots#how-do-i-create-a-bot (retrieved 2026-04-29)
- Telegram Bot Webhooks: https://core.telegram.org/bots/webhooks (retrieved 2026-04-29)
- Telegram Bot API — `getMe`: https://core.telegram.org/bots/api#getme (retrieved 2026-04-29)
- Telegram Bot API — `sendMessage`: https://core.telegram.org/bots/api#sendmessage (retrieved 2026-04-29)
- Telegram Bot API — `Update` object: https://core.telegram.org/bots/api#update (retrieved 2026-04-29)
- Telegram Bot API — `setWebhook`: https://core.telegram.org/bots/api#setwebhook (retrieved 2026-04-29)

These references are also returned at runtime via `GET /_twin/references`, per [twins-la PRINCIPLE 13](https://github.com/twins-la/twins-la/blob/main/PRINCIPLES.md#13-twins-must-be-self-documenting).

### Version

0.2.0 — Initial messaging scenario implementation.
