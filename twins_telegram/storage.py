"""Abstract storage interface for the Telegram twin.

Hosts (local SQLite, cloud Postgres) implement this contract. The twin
package never imports a specific database driver.

Every resource carries a ``tenant_id`` column. Twin Plane operations
scope by ``tenant_id``; Bot-API operations scope by ``bot_id`` (and the
bot row carries the tenant_id).
"""

from abc import ABC, abstractmethod
from typing import Optional


class TwinStorage(ABC):
    """Storage backend contract that hosts must implement."""

    # -- Bots ("accounts" at the Twin Plane layer) --

    @abstractmethod
    def create_bot(
        self,
        *,
        tenant_id: str,
        bot_id: int,
        token: str,
        username: str,
        first_name: str,
    ) -> dict:
        """Create a bot. Returns the stored bot dict (includes tenant_id, token)."""

    @abstractmethod
    def get_bot(self, bot_id: int) -> Optional[dict]:
        """Fetch a bot by id. Returns None if not found."""

    @abstractmethod
    def get_bot_by_token(self, token: str) -> Optional[dict]:
        """Fetch a bot by token. MUST be O(1) — token is the per-request lookup key."""

    @abstractmethod
    def list_bots(self, tenant_id: Optional[str] = None) -> list[dict]:
        """List bots. tenant_id=None returns all (admin only)."""

    # -- Messages --

    @abstractmethod
    def create_message(self, data: dict) -> dict:
        """Persist a message. data MUST include bot_id, tenant_id, chat_id, direction.

        Returns the stored dict; the storage assigns ``message_id`` if
        not provided.
        """

    @abstractmethod
    def list_messages(self, bot_id: int, filters: Optional[dict] = None) -> list[dict]:
        """List messages for a bot, optionally filtered."""

    # -- Webhooks --

    @abstractmethod
    def set_webhook(
        self,
        *,
        bot_id: int,
        url: str,
        secret_token: str,
        allowed_updates: Optional[list[str]] = None,
    ) -> dict:
        """Upsert the webhook config for a bot. Returns the stored record."""

    @abstractmethod
    def get_webhook(self, bot_id: int) -> Optional[dict]:
        """Fetch the webhook config for a bot. Returns None if not set."""

    @abstractmethod
    def delete_webhook(self, bot_id: int, *, drop_pending_updates: bool) -> None:
        """Remove the webhook config for a bot. Optionally drop queued updates."""

    # -- Updates queue --

    @abstractmethod
    def queue_update(self, bot_id: int, update: dict) -> dict:
        """Enqueue an Update for a bot. Returns the stored update (with update_id)."""

    @abstractmethod
    def get_pending_updates(
        self, bot_id: int, *, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        """Return queued updates with update_id >= offset.

        Per Telegram semantics, supplying offset=N implicitly acks updates
        with update_id < N — the storage may drop them on read.
        """

    # -- Feedback --

    @abstractmethod
    def create_feedback(self, data: dict) -> dict:
        """Persist a feedback record. data MUST include id, tenant_id, body, status."""

    @abstractmethod
    def get_feedback(self, feedback_id: str) -> Optional[dict]:
        """Fetch a feedback record by id."""

    @abstractmethod
    def list_feedback(
        self,
        *,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """List feedback, optionally filtered by status and/or tenant."""

    @abstractmethod
    def update_feedback(self, feedback_id: str, updates: dict) -> Optional[dict]:
        """Mutate a feedback record. Returns the updated dict or None."""

    # -- Logs --

    @abstractmethod
    def append_log(self, entry: dict) -> None:
        """Append an operation log entry. entry MUST include tenant_id."""

    @abstractmethod
    def list_logs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Retrieve operation logs, optionally scoped to a tenant."""
