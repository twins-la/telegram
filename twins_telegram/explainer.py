"""Explainer page and agent instructions for the Telegram twin.

Serves:
  GET /                          — HTML explainer page for humans and agents
  GET /_twin/agent-instructions  — Plain-text agent instructions
"""

from flask import Blueprint, Response

explainer_bp = Blueprint("explainer", __name__)

AGENT_INSTRUCTIONS = """\
# Telegram Bot API Twin — telegram.twins.la

A high-fidelity digital twin of the Telegram Bot API. Code written
against this twin works against api.telegram.org with only hostname and
credential changes.

## Authentication

Bot API: token-in-URL
  Path: /bot<token>/<METHOD>
  The token is returned by POST /_twin/accounts.

Twin Plane: HTTP Basic Auth (tenant_id:tenant_secret)
  Bootstrap a tenant first:
    POST /_twin/tenants -> {tenant_id, tenant_secret}
  Then create a bot inside the tenant:
    POST /_twin/accounts (Basic auth) -> {bot_id, token, username, ...}

Twin Plane Admin: Bearer token
  Header: Authorization: Bearer <admin_token>
  Service-wide operations (list all bots, all logs, all feedback)
  require an admin token set by the deployment owner.

## Key Endpoints

Twin Plane (no auth):
  GET  /_twin/health        — status check
  GET  /_twin/scenarios     — supported scenarios
  GET  /_twin/settings      — twin settings
  GET  /_twin/references    — authoritative sources used to build this twin
  POST /_twin/tenants       — bootstrap a tenant (returns id + secret once)

Twin Plane (Basic tenant_id:tenant_secret):
  POST /_twin/accounts          — create a bot inside the tenant
  GET  /_twin/accounts          — list your bots
  GET  /_twin/logs              — your operation logs
  POST /_twin/simulate/inbound  — deliver a synthetic inbound message to a bot
  POST /_twin/feedback          — submit feedback
  GET  /_twin/feedback          — list your feedback

Bot API (token-in-URL):
  GET  /bot<token>/getMe              — return the bot's User object
  POST /bot<token>/sendMessage        — chat_id, text -> Message
  GET  /bot<token>/getUpdates         — return queued Updates
  POST /bot<token>/setWebhook         — url, secret_token, allowed_updates
  POST /bot<token>/deleteWebhook      — drop_pending_updates: bool
  GET  /bot<token>/getWebhookInfo     — current WebhookInfo

## Quick Start

1. Bootstrap a tenant (no auth):
   curl -X POST https://telegram.twins.la/_twin/tenants \\
     -H "Content-Type: application/json" \\
     -d '{"friendly_name": "My App"}'
   # -> { tenant_id, tenant_secret }

2. Create a bot inside the tenant:
   curl -X POST https://telegram.twins.la/_twin/accounts \\
     -u "TENANT_ID:TENANT_SECRET" \\
     -H "Content-Type: application/json" \\
     -d '{"username": "my_bot", "first_name": "My Bot"}'
   # -> { bot_id, token, ... }

3. Send a message:
   curl -X POST "https://telegram.twins.la/bot<TOKEN>/sendMessage" \\
     -H "Content-Type: application/json" \\
     -d '{"chat_id": 123456, "text": "Hello from the twin"}'

4. Set a webhook and simulate inbound:
   curl -X POST "https://telegram.twins.la/bot<TOKEN>/setWebhook" \\
     -d 'url=https://your.example.com/telegram&secret_token=hunter2'

   curl -X POST https://telegram.twins.la/_twin/simulate/inbound \\
     -u "TENANT_ID:TENANT_SECRET" \\
     -H "Content-Type: application/json" \\
     -d '{"bot_id": <BOT_ID>, "from_user_id": 42, "text": "ping"}'

## Local Usage

pip install twins-telegram twins-telegram-local
python -m twins_telegram_local

Then use http://localhost:8080 instead of https://telegram.twins.la.

## Feedback

Submit feedback (Basic tenant auth):
  curl -X POST https://telegram.twins.la/_twin/feedback \\
    -u "TENANT_ID:TENANT_SECRET" \\
    -H "Content-Type: application/json" \\
    -d '{
      "body": "Description of what you encountered",
      "category": "bug",
      "context": {"bot_id": 123, "method": "sendMessage"}
    }'

## Reference

GitHub:           https://github.com/twins-la/telegram
Project overview: https://twins.la
All twins:        https://github.com/twins-la/twins-la
"""


EXPLAINER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>telegram.twins.la &mdash; Telegram Bot API Twin</title>
    <link rel="icon" type="image/png" href="https://twins.la/twins.png">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            min-height: 100vh;
            background: #f8f8f8;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #374151;
            padding: 4rem 2rem;
            line-height: 1.7;
        }
        main { max-width: 700px; margin: 0 auto; }
        h1 {
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 600;
            letter-spacing: -0.03em;
            color: #1a2e4a;
            margin-bottom: 0.5rem;
        }
        h1 .telegram { color: #0088cc; }
        .tagline { font-size: 1.1rem; color: #6b7280; margin-bottom: 2.5rem; font-weight: 300; }
        h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: #1a2e4a;
            margin: 2rem 0 0.75rem;
            letter-spacing: -0.01em;
        }
        p { margin-bottom: 1rem; color: #6b7280; }
        p strong { color: #1a2e4a; }
        a { color: #0088cc; text-decoration: none; }
        a:hover { color: #006699; text-decoration: underline; }
        ul { list-style: none; padding: 0; margin-bottom: 1rem; }
        ul li { padding: 0.3rem 0; color: #6b7280; }
        ul li::before { content: "→ "; color: #0088cc; }
        code {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85em;
            background: #f3f4f6;
            padding: 0.15em 0.4em;
            border-radius: 4px;
            color: #1a2e4a;
            border: 1px solid #e5e7eb;
        }
        .snippet-box {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1rem 0;
            position: relative;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .snippet-box pre {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #6b7280;
            white-space: pre-wrap;
            word-break: break-word;
            line-height: 1.5;
            max-height: 400px;
            overflow-y: auto;
        }
        .copy-btn {
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            background: #f3f4f6;
            color: #6b7280;
            border: 1px solid #e5e7eb;
            padding: 0.3rem 0.7rem;
            border-radius: 6px;
            font-size: 0.75rem;
            cursor: pointer;
            font-family: 'Inter', sans-serif;
            transition: background 0.15s, color 0.15s;
        }
        .copy-btn:hover { background: #1a2e4a; color: #ffffff; }
        .links { margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid #e5e7eb; }
        .links a { margin-right: 1.5rem; font-size: 0.9rem; }
        footer { margin-top: 3rem; color: #6b7280; font-size: 0.8rem; }
        footer .dot { color: #0088cc; }
        .breadcrumb { margin-bottom: 0.5rem; font-size: 0.85rem; }
        .breadcrumb a { color: #0e7490; }
        .breadcrumb a:hover { color: #1a2e4a; }
    </style>
</head>
<body>
    <main>
        <p class="breadcrumb"><a href="https://twins.la">twins.la</a></p>
        <h1><span class="telegram">telegram</span>.twins.la</h1>
        <p class="tagline">A digital twin of the Telegram Bot API.</p>

        <h2>What is this?</h2>
        <p>
            A high-fidelity digital twin of Telegram's Bot API. Code you write
            against this twin will work against the real
            <code>api.telegram.org</code> with only hostname and credential
            changes. No BotFather account needed to develop.
        </p>

        <h2>Supported scenarios</h2>
        <ul>
            <li>Bot identity via <code>getMe</code></li>
            <li>Outbound text messages via <code>sendMessage</code></li>
            <li>Webhook configuration: <code>setWebhook</code> / <code>deleteWebhook</code> / <code>getWebhookInfo</code></li>
            <li>Webhook delivery with <code>X-Telegram-Bot-Api-Secret-Token</code> header</li>
            <li>Update polling via <code>getUpdates</code> (queued, not long-polled)</li>
            <li>Inbound message simulation via Twin Plane</li>
        </ul>

        <h2>How to use it</h2>
        <p>
            <strong>Cloud:</strong> Point your Bot API client at
            <code>https://telegram.twins.la</code> instead of
            <code>api.telegram.org</code>. Bootstrap a tenant via
            <code>POST /_twin/tenants</code>, create a bot via
            <code>POST /_twin/accounts</code>, and use the returned token.
        </p>
        <p>
            <strong>Local:</strong> Install with
            <code>pip install twins-telegram-local</code> and run a local
            instance on any port. Same API, same behavior, your machine.
        </p>

        <h2>For agents</h2>
        <p>
            Copy this into your agent's system prompt, tool configuration, or
            CLAUDE.md. Also available as plain text at
            <a href="/_twin/agent-instructions"><code>/_twin/agent-instructions</code></a>.
        </p>
        <div class="snippet-box">
            <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('agent-snippet').textContent).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)})">Copy</button>
            <pre id="agent-snippet">""" + AGENT_INSTRUCTIONS.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + """</pre>
        </div>

        <div class="links">
            <a href="https://github.com/twins-la/telegram">GitHub</a>
            <a href="https://twins.la">twins.la</a>
            <a href="/_twin/health">Health</a>
            <a href="/_twin/scenarios">Scenarios</a>
        </div>

        <footer>twins.la <span class="dot">&middot;</span> Where agents meet their environment.</footer>
    </main>
</body>
</html>
"""


@explainer_bp.route("/", methods=["GET"])
def explainer_page():
    return EXPLAINER_HTML


@explainer_bp.route("/_twin/agent-instructions", methods=["GET"])
def agent_instructions():
    return Response(AGENT_INSTRUCTIONS, mimetype="text/plain")
