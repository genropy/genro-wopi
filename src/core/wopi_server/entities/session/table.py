# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Session table manager for WOPI editing sessions.

This module provides the SessionsTable class for managing active WOPI editing
sessions. A session is created when Genropy requests document access and
expires after the configured TTL.

Each session tracks:
    - File location (tenant, storage, path)
    - WOPI identifiers (file_id, access_token)
    - Permissions and identity (account, user)
    - Callback context (origin_connection_id, origin_page_id)
    - Lock state for concurrent editing

Example:
    Creating and managing sessions::

        from core.wopi_server.wopi_base import WopiServerBase

        wopi = WopiServerBase(db_path=":memory:")
        await wopi.init()

        sessions = wopi.db.table("sessions")

        # Create session
        session = await sessions.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
            user="Mario Rossi",
        )

        # Lookup by token
        session = await sessions.get_by_token(access_token)
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sql import String, Table, Timestamp


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SessionsTable(Table):
    """WOPI session storage table.

    Manages active editing sessions with expiration, locking, and audit info.

    Attributes:
        name: Table name ("sessions").
        pkey: Primary key column ("id").

    Table Schema:
        - id: Session UUID (primary key)
        - tenant_id: Tenant identifier
        - storage_name: Storage backend name
        - file_path: Document path in storage
        - file_id: WOPI file_id for URLs
        - access_token: WOPI access token (JWT or opaque)
        - permissions: JSON list ["view"] or ["view", "edit"]
        - account: Account for audit (required)
        - user: User name (optional, for collaborative editing)
        - origin_connection_id: Genropy connection for callbacks
        - origin_page_id: Genropy page context
        - lock_id: Current lock ID (if locked)
        - lock_expires_at: Lock expiration timestamp
        - created_at: Session creation time
        - expires_at: Session expiration time
        - last_accessed_at: Last WOPI operation time
    """

    name = "sessions"
    pkey = "id"

    def configure(self) -> None:
        """Define table columns."""
        c = self.columns
        c.column("id", String)
        c.column("tenant_id", String)
        c.column("storage_name", String)
        c.column("file_path", String)
        c.column("file_id", String)
        c.column("access_token", String)
        c.column("permissions", String, json_encoded=True)
        c.column("account", String)
        c.column("user", String)
        c.column("origin_connection_id", String)
        c.column("origin_page_id", String)
        c.column("lock_id", String)
        c.column("lock_expires_at", Timestamp)
        c.column("created_at", Timestamp, default="CURRENT_TIMESTAMP")
        c.column("expires_at", Timestamp)
        c.column("last_accessed_at", Timestamp)

    async def create_session(
        self,
        tenant_id: str,
        storage_name: str,
        file_path: str,
        permissions: list[str],
        account: str,
        user: str | None = None,
        origin_connection_id: str | None = None,
        origin_page_id: str | None = None,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Create a new WOPI session.

        Args:
            tenant_id: Tenant identifier.
            storage_name: Storage backend name.
            file_path: Document path in storage.
            permissions: List of permissions (["view"] or ["view", "edit"]).
            account: Account for audit (required).
            user: User name (optional, for collaborative editing).
            origin_connection_id: Genropy connection ID for callbacks.
            origin_page_id: Genropy page context.
            ttl_seconds: Session TTL in seconds (default 3600).

        Returns:
            Session dict with id, file_id, access_token, expires_at.
        """
        session_id = self._generate_id()
        file_id = self._generate_file_id()
        access_token = self._generate_token()
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        data = {
            "id": session_id,
            "tenant_id": tenant_id,
            "storage_name": storage_name,
            "file_path": file_path,
            "file_id": file_id,
            "access_token": access_token,
            "permissions": permissions,
            "account": account,
            "user": user,
            "origin_connection_id": origin_connection_id,
            "origin_page_id": origin_page_id,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "last_accessed_at": now.isoformat(),
        }

        await self.insert(data)
        session = await self.get(session_id)
        if session is None:
            raise RuntimeError(f"Failed to create session {session_id}")
        return session

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        return f"sess_{secrets.token_urlsafe(16)}"

    def _generate_file_id(self) -> str:
        """Generate a unique WOPI file_id."""
        return f"file_{secrets.token_urlsafe(16)}"

    def _generate_token(self) -> str:
        """Generate a secure access token."""
        return secrets.token_urlsafe(32)

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session dict or None if not found.
        """
        return await self.select_one(where={"id": session_id})

    async def get_by_token(self, access_token: str) -> dict[str, Any] | None:
        """Fetch a session by access token.

        Args:
            access_token: WOPI access token.

        Returns:
            Session dict or None if not found.
        """
        return await self.select_one(where={"access_token": access_token})

    async def get_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        """Fetch a session by WOPI file_id.

        Args:
            file_id: WOPI file_id.

        Returns:
            Session dict or None if not found.
        """
        return await self.select_one(where={"file_id": file_id})

    async def update_last_accessed(self, session_id: str) -> None:
        """Update last_accessed_at timestamp.

        Args:
            session_id: Session identifier.
        """
        now = _utcnow().isoformat()
        await self.update({"last_accessed_at": now}, where={"id": session_id})

    async def set_lock(
        self, session_id: str, lock_id: str, ttl_seconds: int = 1800
    ) -> bool:
        """Set lock on session.

        Args:
            session_id: Session identifier.
            lock_id: Lock identifier from WOPI client.
            ttl_seconds: Lock TTL in seconds (default 30 min).

        Returns:
            True if lock acquired, False if already locked by different ID.
        """
        session = await self.get(session_id)
        if not session:
            return False

        current_lock = session.get("lock_id")
        current_expires = session.get("lock_expires_at")

        # Check if already locked by different ID
        if current_lock and current_lock != lock_id:
            if current_expires:
                expires_dt = self._parse_timestamp(current_expires)
                if expires_dt > _utcnow():
                    return False  # Lock still valid

        # Set or refresh lock
        expires_at = _utcnow() + timedelta(seconds=ttl_seconds)
        await self.update(
            {"lock_id": lock_id, "lock_expires_at": expires_at.isoformat()},
            where={"id": session_id},
        )
        return True

    async def release_lock(self, session_id: str, lock_id: str) -> bool:
        """Release lock on session.

        Args:
            session_id: Session identifier.
            lock_id: Lock identifier (must match current lock).

        Returns:
            True if released, False if lock_id doesn't match.
        """
        session = await self.get(session_id)
        if not session:
            return False

        current_lock = session.get("lock_id")
        if current_lock and current_lock != lock_id:
            return False

        await self.update(
            {"lock_id": None, "lock_expires_at": None},
            where={"id": session_id},
        )
        return True

    async def get_lock(self, session_id: str) -> str | None:
        """Get current lock_id.

        Args:
            session_id: Session identifier.

        Returns:
            Current lock_id or None if not locked.
        """
        session = await self.get(session_id)
        if not session:
            return None

        lock_id = session.get("lock_id")
        if not lock_id:
            return None

        # Check if lock expired
        lock_expires = session.get("lock_expires_at")
        if lock_expires:
            expires_dt = self._parse_timestamp(lock_expires)
            if expires_dt <= _utcnow():
                # Lock expired, clear it
                await self.update(
                    {"lock_id": None, "lock_expires_at": None},
                    where={"id": session_id},
                )
                return None

        return lock_id

    def _parse_timestamp(self, ts: str | datetime) -> datetime:
        """Parse timestamp string to datetime."""
        if isinstance(ts, datetime):
            return ts
        return datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))

    async def is_expired(self, session_id: str) -> bool:
        """Check if session is expired.

        Args:
            session_id: Session identifier.

        Returns:
            True if expired, False otherwise.
        """
        session = await self.get(session_id)
        if not session:
            return True

        expires_at = session.get("expires_at")
        if not expires_at:
            return True

        expires_dt = self._parse_timestamp(expires_at)
        return expires_dt <= _utcnow()

    async def cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions deleted.
        """
        now = _utcnow().isoformat()
        # Delete sessions where expires_at <= now
        result = await self.db.adapter.execute(
            f"DELETE FROM {self.name} WHERE expires_at <= ?",
            {"expires_at": now},
        )
        return result

    async def list_active(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List active (non-expired) sessions.

        Args:
            tenant_id: Optional filter by tenant.

        Returns:
            List of active session dicts.
        """
        now = _utcnow().isoformat()
        where = {}
        if tenant_id:
            where["tenant_id"] = tenant_id

        sessions = await self.select(where=where if where else None, order_by="created_at DESC")
        return [s for s in sessions if s.get("expires_at", "") > now]

    async def remove(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        result = await self.delete(where={"id": session_id})
        return result > 0


__all__ = ["SessionsTable"]
