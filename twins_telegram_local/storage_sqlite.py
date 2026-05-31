"""SQLite implementation of the Telegram twin's TwinStorage.

Provides persistent storage for the Telegram twin using SQLite. The
database file is configurable via ``TWIN_DB_PATH``.

Every resource table carries a ``tenant_id`` column. Twin Plane
operations scope by ``tenant_id``; Bot-API operations scope by
``bot_id``, and the bot row carries the tenant_id so the Twin Plane can
still enforce isolation.
"""

import json
import sqlite3
import threading
from typing import Optional

from twins_telegram.storage import TwinStorage


_VALID_FEEDBACK_COLUMNS = frozenset({"status", "date_updated"})


class SQLiteStorage(TwinStorage):
    """SQLite-backed storage for the Telegram twin.

    Thread-safe via a per-instance lock. Uses WAL mode for concurrent
    reads.
    """

    def __init__(self, db_path: str = "data/twin.db"):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS bots (
                        id INTEGER PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        token TEXT NOT NULL UNIQUE,
                        username TEXT NOT NULL DEFAULT '',
                        first_name TEXT NOT NULL DEFAULT '',
                        date_created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_bots_tenant ON bots(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_bots_token ON bots(token);

                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL,
                        bot_id INTEGER NOT NULL,
                        tenant_id TEXT NOT NULL,
                        chat_id INTEGER NOT NULL,
                        from_json TEXT NOT NULL DEFAULT '{}',
                        chat_json TEXT NOT NULL DEFAULT '{}',
                        text TEXT NOT NULL DEFAULT '',
                        direction TEXT NOT NULL DEFAULT 'outbound',
                        date INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY (bot_id) REFERENCES bots(id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_messages_bot ON messages(bot_id);
                    CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(bot_id, chat_id);

                    CREATE TABLE IF NOT EXISTS webhooks (
                        bot_id INTEGER PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        url TEXT NOT NULL,
                        secret_token TEXT NOT NULL DEFAULT '',
                        allowed_updates_json TEXT NOT NULL DEFAULT 'null',
                        date_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (bot_id) REFERENCES bots(id)
                    );

                    CREATE TABLE IF NOT EXISTS updates (
                        update_id INTEGER NOT NULL,
                        bot_id INTEGER NOT NULL,
                        tenant_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        delivered INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (bot_id, update_id),
                        FOREIGN KEY (bot_id) REFERENCES bots(id)
                    );

                    CREATE TABLE IF NOT EXISTS feedback (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        body TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT '',
                        context_json TEXT NOT NULL DEFAULT '{}',
                        status TEXT NOT NULL DEFAULT 'pending',
                        date_created TEXT NOT NULL,
                        date_updated TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON feedback(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);

                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_logs_tenant ON logs(tenant_id);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    # -- Bots --

    def create_bot(
        self,
        *,
        tenant_id: str,
        bot_id: int,
        token: str,
        username: str,
        first_name: str,
    ) -> dict:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO bots (id, tenant_id, token, username, first_name) VALUES (?, ?, ?, ?, ?)",
                    (bot_id, tenant_id, token, username, first_name),
                )
                conn.commit()
            finally:
                conn.close()
        return {
            "id": bot_id,
            "tenant_id": tenant_id,
            "token": token,
            "username": username,
            "first_name": first_name,
        }

    def get_bot(self, bot_id: int) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_bot_by_token(self, token: str) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM bots WHERE token = ?", (token,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_bots(self, tenant_id: Optional[str] = None) -> list[dict]:
        conn = self._get_conn()
        try:
            if tenant_id is None:
                rows = conn.execute("SELECT * FROM bots ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bots WHERE tenant_id = ? ORDER BY id", (tenant_id,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -- Messages --

    def create_message(self, data: dict) -> dict:
        bot_id = int(data["bot_id"])
        chat_id = int(data["chat_id"])
        with self._lock:
            conn = self._get_conn()
            try:
                next_message_id = conn.execute(
                    "SELECT COALESCE(MAX(message_id), 0) + 1 FROM messages WHERE bot_id = ? AND chat_id = ?",
                    (bot_id, chat_id),
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO messages
                        (message_id, bot_id, tenant_id, chat_id, from_json, chat_json, text, direction, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        next_message_id,
                        bot_id,
                        data["tenant_id"],
                        chat_id,
                        json.dumps(data.get("from", {}) or {}),
                        json.dumps(data.get("chat", {}) or {}),
                        data.get("text", ""),
                        data.get("direction", "outbound"),
                        int(data.get("date", 0)),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return {
            "message_id": next_message_id,
            "bot_id": bot_id,
            "tenant_id": data["tenant_id"],
            "chat_id": chat_id,
            "from": data.get("from", {}),
            "chat": data.get("chat", {}),
            "text": data.get("text", ""),
            "direction": data.get("direction", "outbound"),
            "date": data.get("date", 0),
        }

    def list_messages(self, bot_id: int, filters: Optional[dict] = None) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM messages WHERE bot_id = ? ORDER BY id", (bot_id,)
            ).fetchall()
            return [self._row_to_message(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_message(row) -> dict:
        return {
            "message_id": row["message_id"],
            "bot_id": row["bot_id"],
            "tenant_id": row["tenant_id"],
            "chat_id": row["chat_id"],
            "from": json.loads(row["from_json"] or "{}"),
            "chat": json.loads(row["chat_json"] or "{}"),
            "text": row["text"],
            "direction": row["direction"],
            "date": row["date"],
        }

    # -- Webhooks --

    def set_webhook(
        self,
        *,
        bot_id: int,
        url: str,
        secret_token: str,
        allowed_updates: Optional[list[str]] = None,
    ) -> dict:
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"bot {bot_id} not found")
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO webhooks (bot_id, tenant_id, url, secret_token, allowed_updates_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        url = excluded.url,
                        secret_token = excluded.secret_token,
                        allowed_updates_json = excluded.allowed_updates_json,
                        date_updated = CURRENT_TIMESTAMP
                    """,
                    (
                        bot_id,
                        bot["tenant_id"],
                        url,
                        secret_token,
                        json.dumps(allowed_updates),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_webhook(bot_id) or {}

    def get_webhook(self, bot_id: int) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM webhooks WHERE bot_id = ?", (bot_id,)
            ).fetchone()
            if not row:
                return None
            pending = conn.execute(
                "SELECT COUNT(*) FROM updates WHERE bot_id = ? AND delivered = 0",
                (bot_id,),
            ).fetchone()[0]
            return {
                "bot_id": row["bot_id"],
                "tenant_id": row["tenant_id"],
                "url": row["url"],
                "secret_token": row["secret_token"],
                "allowed_updates": json.loads(row["allowed_updates_json"] or "null"),
                "pending_update_count": pending,
            }
        finally:
            conn.close()

    def delete_webhook(self, bot_id: int, *, drop_pending_updates: bool) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM webhooks WHERE bot_id = ?", (bot_id,))
                if drop_pending_updates:
                    conn.execute("DELETE FROM updates WHERE bot_id = ?", (bot_id,))
                conn.commit()
            finally:
                conn.close()

    # -- Updates queue --

    def queue_update(self, bot_id: int, update: dict) -> dict:
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"bot {bot_id} not found")
        with self._lock:
            conn = self._get_conn()
            try:
                next_update_id = conn.execute(
                    "SELECT COALESCE(MAX(update_id), 0) + 1 FROM updates WHERE bot_id = ?",
                    (bot_id,),
                ).fetchone()[0]
                payload = {"update_id": next_update_id, **update}
                conn.execute(
                    "INSERT INTO updates (update_id, bot_id, tenant_id, payload_json) VALUES (?, ?, ?, ?)",
                    (next_update_id, bot_id, bot["tenant_id"], json.dumps(payload)),
                )
                conn.commit()
            finally:
                conn.close()
        return payload

    def get_pending_updates(
        self, bot_id: int, *, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if offset > 0:
                    conn.execute(
                        "DELETE FROM updates WHERE bot_id = ? AND update_id < ?",
                        (bot_id, offset),
                    )
                    conn.commit()
                rows = conn.execute(
                    "SELECT payload_json FROM updates WHERE bot_id = ? AND update_id >= ? "
                    "ORDER BY update_id LIMIT ?",
                    (bot_id, offset, limit),
                ).fetchall()
                return [json.loads(r["payload_json"]) for r in rows]
            finally:
                conn.close()

    # -- Feedback --

    def create_feedback(self, data: dict) -> dict:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO feedback
                        (id, tenant_id, body, category, context_json, status, date_created, date_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["id"],
                        data["tenant_id"],
                        data["body"],
                        data.get("category", ""),
                        json.dumps(data.get("context", {}) or {}),
                        data.get("status", "pending"),
                        data["date_created"],
                        data["date_updated"],
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_feedback(data["id"])

    def get_feedback(self, feedback_id: str) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
            ).fetchone()
            return self._row_to_feedback(row) if row else None
        finally:
            conn.close()

    def list_feedback(
        self,
        *,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM feedback WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if tenant_id is not None:
                sql += " AND tenant_id = ?"
                params.append(tenant_id)
            sql += " ORDER BY date_created DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_feedback(r) for r in rows]
        finally:
            conn.close()

    def update_feedback(self, feedback_id: str, updates: dict) -> Optional[dict]:
        cols = [k for k in updates.keys() if k in _VALID_FEEDBACK_COLUMNS]
        if not cols:
            return self.get_feedback(feedback_id)
        sql = f"UPDATE feedback SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?"
        params = [updates[c] for c in cols] + [feedback_id]
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()
        return self.get_feedback(feedback_id)

    @staticmethod
    def _row_to_feedback(row) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "body": row["body"],
            "category": row["category"],
            "context": json.loads(row["context_json"] or "{}"),
            "status": row["status"],
            "date_created": row["date_created"],
            "date_updated": row["date_updated"],
        }

    # -- Logs --

    def append_log(self, entry: dict) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO logs (tenant_id, record_json, timestamp) VALUES (?, ?, ?)",
                    (entry.get("tenant_id", ""), json.dumps(entry), entry.get("timestamp", "")),
                )
                conn.commit()
            finally:
                conn.close()

    def list_logs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        conn = self._get_conn()
        try:
            sql = "SELECT id, record_json FROM logs"
            params: list = []
            if tenant_id is not None:
                sql += " WHERE tenant_id = ?"
                params.append(tenant_id)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            out = []
            for r in rows:
                rec = json.loads(r["record_json"])
                rec["id"] = r["id"]
                out.append(rec)
            return out
        finally:
            conn.close()
