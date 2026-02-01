# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for SessionsTable.

Tests cover session CRUD operations, token/file_id lookups, locking,
expiration handling, and cleanup.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from core.wopi_server.wopi_base import WopiServerBase
from core.wopi_server.wopi_config import WopiConfig


@pytest.fixture
async def db(tmp_path):
    """Create database with schema only (no init logic)."""
    server = WopiServerBase(WopiConfig(db_path=str(tmp_path / "test.db")))
    await server.db.connect()
    await server.db.check_structure()
    yield server.db
    await server.close()


@pytest.fixture
async def sessions_table(db):
    """Get sessions table from database."""
    return db.table("sessions")


class TestSessionCreation:
    """Tests for session creation."""

    async def test_create_session_basic(self, sessions_table):
        """Create a session with required fields."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )

        assert session["id"].startswith("sess_")
        assert session["file_id"].startswith("file_")
        assert session["access_token"] is not None
        assert session["tenant_id"] == "acme"
        assert session["storage_name"] == "attachments"
        assert session["file_path"] == "docs/report.xlsx"
        assert session["permissions"] == ["view"]
        assert session["account"] == "sales"
        assert session["user"] is None

    async def test_create_session_with_user(self, sessions_table):
        """Create a session with optional user field."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
            user="Mario Rossi",
        )

        assert session["user"] == "Mario Rossi"
        assert session["permissions"] == ["view", "edit"]

    async def test_create_session_with_callback_context(self, sessions_table):
        """Create a session with Genropy callback context."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
            origin_connection_id="conn_abc123",
            origin_page_id="ordini_detail_12345",
        )

        assert session["origin_connection_id"] == "conn_abc123"
        assert session["origin_page_id"] == "ordini_detail_12345"

    async def test_create_session_custom_ttl(self, sessions_table):
        """Create a session with custom TTL."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
            ttl_seconds=7200,  # 2 hours
        )

        created = datetime.fromisoformat(session["created_at"])
        expires = datetime.fromisoformat(session["expires_at"])
        delta = expires - created

        # Should be approximately 2 hours
        assert 7190 <= delta.total_seconds() <= 7210

    async def test_create_session_generates_unique_ids(self, sessions_table):
        """Each session gets unique identifiers."""
        sessions = []
        for _ in range(5):
            session = await sessions_table.create_session(
                tenant_id="acme",
                storage_name="attachments",
                file_path="docs/report.xlsx",
                permissions=["view"],
                account="sales",
            )
            sessions.append(session)

        ids = [s["id"] for s in sessions]
        file_ids = [s["file_id"] for s in sessions]
        tokens = [s["access_token"] for s in sessions]

        assert len(set(ids)) == 5
        assert len(set(file_ids)) == 5
        assert len(set(tokens)) == 5


class TestSessionLookup:
    """Tests for session lookup methods."""

    async def test_get_by_id(self, sessions_table):
        """Fetch session by ID."""
        created = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )

        fetched = await sessions_table.get(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_by_token(self, sessions_table):
        """Fetch session by access token."""
        created = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )

        fetched = await sessions_table.get_by_token(created["access_token"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_by_file_id(self, sessions_table):
        """Fetch session by WOPI file_id."""
        created = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )

        fetched = await sessions_table.get_by_file_id(created["file_id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_nonexistent_returns_none(self, sessions_table):
        """Lookup of nonexistent session returns None."""
        assert await sessions_table.get("nonexistent") is None
        assert await sessions_table.get_by_token("nonexistent") is None
        assert await sessions_table.get_by_file_id("nonexistent") is None


class TestSessionLocking:
    """Tests for session locking mechanism."""

    async def test_set_lock(self, sessions_table):
        """Set a lock on a session."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        result = await sessions_table.set_lock(session["id"], "lock_123")
        assert result is True

        lock_id = await sessions_table.get_lock(session["id"])
        assert lock_id == "lock_123"

    async def test_set_lock_same_id_refreshes(self, sessions_table):
        """Setting lock with same ID refreshes expiration."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        await sessions_table.set_lock(session["id"], "lock_123")
        result = await sessions_table.set_lock(session["id"], "lock_123")
        assert result is True

    async def test_set_lock_different_id_fails(self, sessions_table):
        """Setting lock with different ID fails if lock is active."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        await sessions_table.set_lock(session["id"], "lock_123")
        result = await sessions_table.set_lock(session["id"], "lock_456")
        assert result is False

        lock_id = await sessions_table.get_lock(session["id"])
        assert lock_id == "lock_123"

    async def test_release_lock(self, sessions_table):
        """Release a lock on a session."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        await sessions_table.set_lock(session["id"], "lock_123")
        result = await sessions_table.release_lock(session["id"], "lock_123")
        assert result is True

        lock_id = await sessions_table.get_lock(session["id"])
        assert lock_id is None

    async def test_release_lock_wrong_id_fails(self, sessions_table):
        """Releasing with wrong lock ID fails."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        await sessions_table.set_lock(session["id"], "lock_123")
        result = await sessions_table.release_lock(session["id"], "lock_456")
        assert result is False

        lock_id = await sessions_table.get_lock(session["id"])
        assert lock_id == "lock_123"

    async def test_get_lock_nonexistent_session(self, sessions_table):
        """Getting lock from nonexistent session returns None."""
        lock_id = await sessions_table.get_lock("nonexistent")
        assert lock_id is None

    async def test_set_lock_nonexistent_session(self, sessions_table):
        """Setting lock on nonexistent session returns False."""
        result = await sessions_table.set_lock("nonexistent", "lock_123")
        assert result is False


class TestSessionExpiration:
    """Tests for session expiration handling."""

    async def test_is_expired_false_for_active(self, sessions_table):
        """Active session is not expired."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
            ttl_seconds=3600,
        )

        is_expired = await sessions_table.is_expired(session["id"])
        assert is_expired is False

    async def test_is_expired_nonexistent(self, sessions_table):
        """Nonexistent session is considered expired."""
        is_expired = await sessions_table.is_expired("nonexistent")
        assert is_expired is True

    async def test_list_active_sessions(self, sessions_table):
        """List only active (non-expired) sessions."""
        # Create some sessions
        await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/file1.xlsx",
            permissions=["view"],
            account="sales",
        )
        await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/file2.xlsx",
            permissions=["view"],
            account="sales",
        )

        active = await sessions_table.list_active()
        assert len(active) == 2

    async def test_list_active_by_tenant(self, sessions_table):
        """Filter active sessions by tenant."""
        await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/file1.xlsx",
            permissions=["view"],
            account="sales",
        )
        await sessions_table.create_session(
            tenant_id="other",
            storage_name="attachments",
            file_path="docs/file2.xlsx",
            permissions=["view"],
            account="sales",
        )

        acme_sessions = await sessions_table.list_active(tenant_id="acme")
        assert len(acme_sessions) == 1
        assert acme_sessions[0]["tenant_id"] == "acme"


class TestSessionOperations:
    """Tests for session update and delete operations."""

    async def test_update_last_accessed(self, sessions_table):
        """Update last_accessed_at timestamp."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )
        original_accessed = session["last_accessed_at"]

        await asyncio.sleep(0.1)
        await sessions_table.update_last_accessed(session["id"])

        updated = await sessions_table.get(session["id"])
        assert updated["last_accessed_at"] > original_accessed

    async def test_remove_session(self, sessions_table):
        """Delete a session."""
        session = await sessions_table.create_session(
            tenant_id="acme",
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view"],
            account="sales",
        )

        result = await sessions_table.remove(session["id"])
        assert result is True

        fetched = await sessions_table.get(session["id"])
        assert fetched is None

    async def test_remove_nonexistent(self, sessions_table):
        """Deleting nonexistent session returns False."""
        result = await sessions_table.remove("nonexistent")
        assert result is False


__all__ = []
