# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for SessionEndpoint - direct endpoint tests for coverage.

These tests directly exercise SessionEndpoint methods to cover
edge cases and error paths.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.wopi_server.entities.session.endpoint import SessionEndpoint


@pytest.fixture
def mock_table():
    """Create mock SessionsTable."""
    table = MagicMock()
    table.create_session = AsyncMock(return_value={
        "session_id": "sess-123",
        "file_id": "file-456",
        "access_token": "token-789",
        "expires_at": "2025-01-01T12:00:00",
    })
    table.get = AsyncMock(return_value={
        "id": "sess-123",
        "tenant_id": "default",
        "file_id": "file-456",
    })
    table.list_active = AsyncMock(return_value=[])
    table.remove = AsyncMock(return_value=True)
    table.cleanup_expired = AsyncMock(return_value=5)
    table.select = AsyncMock(return_value=[])
    return table


@pytest.fixture
def endpoint(mock_table):
    """Create SessionEndpoint with mock table."""
    return SessionEndpoint(mock_table)


class TestSessionEndpointCreate:
    """Tests for SessionEndpoint.create() method."""

    async def test_create_session_basic(self, endpoint, mock_table):
        """create() calls table.create_session with correct args."""
        result = await endpoint.create(
            storage_name="attachments",
            file_path="docs/report.xlsx",
            permissions=["view", "edit"],
            account="sales",
        )

        assert result["session_id"] == "sess-123"
        assert result["file_id"] == "file-456"
        assert result["access_token"] == "token-789"

        mock_table.create_session.assert_called_once()
        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["storage_name"] == "attachments"
        assert call_kwargs["file_path"] == "docs/report.xlsx"
        assert call_kwargs["permissions"] == ["view", "edit"]
        assert call_kwargs["account"] == "sales"

    async def test_create_session_with_user(self, endpoint, mock_table):
        """create() passes user parameter to table."""
        await endpoint.create(
            storage_name="docs",
            file_path="file.docx",
            permissions=["view"],
            account="hr",
            user="Mario Rossi",
        )

        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["user"] == "Mario Rossi"

    async def test_create_session_with_callback_context(self, endpoint, mock_table):
        """create() passes origin_connection_id and origin_page_id."""
        await endpoint.create(
            storage_name="docs",
            file_path="file.docx",
            permissions=["view"],
            account="hr",
            origin_connection_id="conn-abc",
            origin_page_id="page-xyz",
        )

        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["origin_connection_id"] == "conn-abc"
        assert call_kwargs["origin_page_id"] == "page-xyz"

    async def test_create_session_custom_ttl(self, endpoint, mock_table):
        """create() passes custom ttl_seconds."""
        await endpoint.create(
            storage_name="docs",
            file_path="file.docx",
            permissions=["view"],
            account="hr",
            ttl_seconds=7200,
        )

        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["ttl_seconds"] == 7200

    async def test_create_session_uses_default_tenant(self, endpoint, mock_table):
        """create() uses 'default' tenant when not set."""
        await endpoint.create(
            storage_name="docs",
            file_path="file.docx",
            permissions=["view"],
            account="hr",
        )

        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["tenant_id"] == "default"

    async def test_create_session_uses_current_tenant(self, endpoint, mock_table):
        """create() uses _current_tenant_id when set."""
        endpoint._current_tenant_id = "acme"

        await endpoint.create(
            storage_name="docs",
            file_path="file.docx",
            permissions=["view"],
            account="hr",
        )

        call_kwargs = mock_table.create_session.call_args.kwargs
        assert call_kwargs["tenant_id"] == "acme"


class TestSessionEndpointGet:
    """Tests for SessionEndpoint.get() method."""

    async def test_get_existing_session(self, endpoint, mock_table):
        """get() returns session dict for existing session."""
        result = await endpoint.get("sess-123")

        assert result["id"] == "sess-123"
        assert result["tenant_id"] == "default"
        mock_table.get.assert_called_once_with("sess-123")

    async def test_get_not_found_raises(self, endpoint, mock_table):
        """get() raises ValueError when session not found."""
        mock_table.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Session 'nonexistent' not found"):
            await endpoint.get("nonexistent")


class TestSessionEndpointList:
    """Tests for SessionEndpoint.list() method."""

    async def test_list_all_sessions(self, endpoint, mock_table):
        """list() returns all active sessions."""
        mock_table.list_active = AsyncMock(return_value=[
            {"id": "s1", "tenant_id": "default"},
            {"id": "s2", "tenant_id": "acme"},
        ])

        result = await endpoint.list()

        assert len(result) == 2
        mock_table.list_active.assert_called_once_with(tenant_id=None)

    async def test_list_by_tenant(self, endpoint, mock_table):
        """list() filters by tenant_id."""
        mock_table.list_active = AsyncMock(return_value=[
            {"id": "s1", "tenant_id": "acme"},
        ])

        result = await endpoint.list(tenant_id="acme")

        assert len(result) == 1
        mock_table.list_active.assert_called_once_with(tenant_id="acme")


class TestSessionEndpointClose:
    """Tests for SessionEndpoint.close() method."""

    async def test_close_existing_session(self, endpoint, mock_table):
        """close() returns True for existing session."""
        result = await endpoint.close("sess-123")

        assert result is True
        mock_table.remove.assert_called_once_with("sess-123")

    async def test_close_nonexistent_session(self, endpoint, mock_table):
        """close() returns False for nonexistent session."""
        mock_table.remove = AsyncMock(return_value=False)

        result = await endpoint.close("nonexistent")

        assert result is False


class TestSessionEndpointCleanup:
    """Tests for SessionEndpoint.cleanup() method."""

    async def test_cleanup_deletes_expired(self, endpoint, mock_table):
        """cleanup() returns count of deleted sessions."""
        result = await endpoint.cleanup()

        assert result["deleted"] == 5
        mock_table.cleanup_expired.assert_called_once()

    async def test_cleanup_dry_run(self, endpoint, mock_table):
        """cleanup(dry_run=True) counts without deleting."""
        expired_time = "2020-01-01T00:00:00"  # In the past

        mock_table.select = AsyncMock(return_value=[
            {"id": "s1", "expires_at": expired_time},
            {"id": "s2", "expires_at": expired_time},
            {"id": "s3", "expires_at": "2099-01-01T00:00:00"},  # Future
        ])

        result = await endpoint.cleanup(dry_run=True)

        assert result["deleted"] == 0
        assert result["would_delete"] == 2
        mock_table.cleanup_expired.assert_not_called()

    async def test_cleanup_dry_run_no_expired(self, endpoint, mock_table):
        """cleanup(dry_run=True) returns 0 when no expired sessions."""
        mock_table.select = AsyncMock(return_value=[
            {"id": "s1", "expires_at": "2099-01-01T00:00:00"},
        ])

        result = await endpoint.cleanup(dry_run=True)

        assert result["deleted"] == 0
        assert result["would_delete"] == 0
