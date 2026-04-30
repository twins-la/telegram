# Telegram Twin

A digital twin of the [Telegram Bot API](https://core.telegram.org/bots/api) for [twins.la](https://twins.la).

## What This Is

A Python package that emulates the Telegram Bot API with high fidelity within the supported messaging scenario. Existing Bot API client code can be pointed at this twin by changing only the hostname and the bot token. The twin synthesises message delivery and webhook calls internally — no real Telegram or BotFather account is required.

## Supported Scenarios

See [SCENARIOS.md](SCENARIOS.md) for the full scope and authoritative references.

- **Messaging** — `getMe`, `sendMessage` (text), `getUpdates`, `setWebhook` / `deleteWebhook` / `getWebhookInfo`, plus inbound message simulation via the Twin Plane.

## Usage

This package is not run directly. It is loaded by a host:

- **Local**: `twins-telegram-local` (sibling package under `twins_telegram_local/`) — run via gunicorn or `python -m twins_telegram_local`.
- **Cloud**: available at [telegram.twins.la](https://telegram.twins.la).

## Quick Start (local)

```bash
pip install -e . ./twins_telegram_local/
python -m twins_telegram_local
```

Then use the Bot API directly:

```bash
# Bootstrap a tenant
curl -X POST http://localhost:8080/_twin/tenants \
  -H "Content-Type: application/json" \
  -d '{"friendly_name": "Dev"}'
# -> { "tenant_id": "...", "tenant_secret": "..." }

# Create a bot inside the tenant
curl -X POST http://localhost:8080/_twin/accounts \
  -u "TENANT_ID:TENANT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"username": "my_bot"}'
# -> { "bot_id": ..., "token": "...", "username": "my_bot", ... }

# Send a message (token-in-URL)
curl -X POST "http://localhost:8080/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": 123, "text": "Hello from the twin"}'
```

The Twin Plane (`/_twin/*`) is documented in [twins-la/TWIN_PLANE.md](https://github.com/twins-la/twins-la/blob/main/TWIN_PLANE.md).

## License

MIT — see [LICENSE](LICENSE).
