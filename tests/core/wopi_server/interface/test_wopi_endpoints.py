# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for WOPI protocol endpoints.

These tests verify the WOPI CheckFileInfo, GetFile, and PutFile endpoints
work correctly, with special attention to UTC datetime handling.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.wopi_server.interface.api_base import _register_wopi_endpoints


def _utcnow() -> datetime:
    """Return current UTC time (naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def mock_svc():
    """Create mock WopiProxy service."""
    svc = MagicMock()
    svc.db = MagicMock()
    return svc


@pytest.fixture
def mock_sessions_table():
    """Create mock sessions table."""
    table = MagicMock()
    table.get_by_file_id = AsyncMock(return_value=None)
    return table


@pytest.fixture
def mock_storages_table():
    """Create mock storages table."""
    table = MagicMock()
    table.get_storage_manager = AsyncMock()
    return table


@pytest.fixture
def app_with_wopi(mock_svc, mock_sessions_table, mock_storages_table):
    """Create FastAPI app with WOPI endpoints registered."""
    mock_svc.db.table = MagicMock(side_effect=lambda name: {
        "sessions": mock_sessions_table,
        "storages": mock_storages_table,
    }[name])

    app = FastAPI()
    _register_wopi_endpoints(app, mock_svc)
    return app, mock_sessions_table, mock_storages_table


class TestWopiCheckFileInfo:
    """Tests for WOPI CheckFileInfo endpoint."""

    def test_file_not_found_returns_404(self, app_with_wopi):
        """CheckFileInfo returns 404 when session not found."""
        app, sessions_table, _ = app_with_wopi
        sessions_table.get_by_file_id = AsyncMock(return_value=None)

        client = TestClient(app)
        response = client.get("/wopi/files/nonexistent?access_token=token123")

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    def test_invalid_token_returns_401(self, app_with_wopi):
        """CheckFileInfo returns 401 when access token doesn't match."""
        app, sessions_table, _ = app_with_wopi
        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "correct_token",
            "expires_at": (_utcnow() + timedelta(hours=1)).isoformat(),
        })

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=wrong_token")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid access token"

    def test_expired_session_returns_401(self, app_with_wopi):
        """CheckFileInfo returns 401 when session is expired."""
        app, sessions_table, _ = app_with_wopi
        # Session expired 1 hour ago (UTC)
        expired_time = (_utcnow() - timedelta(hours=1)).isoformat()
        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": expired_time,
        })

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        assert response.status_code == 401
        assert response.json()["detail"] == "Session expired"

    def test_valid_session_returns_file_info(self, app_with_wopi):
        """CheckFileInfo returns file metadata for valid session."""
        app, sessions_table, storages_table = app_with_wopi

        # Valid session expiring in 1 hour (UTC)
        valid_expiry = (_utcnow() + timedelta(hours=1)).isoformat()
        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": valid_expiry,
            "tenant_id": "acme",
            "storage_name": "HOME",
            "file_path": "/docs/test.docx",
            "account": "user1",
            "user": "Test User",
        })

        # Mock storage manager and node
        mock_node = MagicMock()
        mock_node.exists = AsyncMock(return_value=True)
        mock_node.size = AsyncMock(return_value=12345)
        mock_node.basename = "test.docx"
        mock_node.mtime = AsyncMock(return_value=1700000000.0)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        assert response.status_code == 200
        data = response.json()
        assert data["BaseFileName"] == "test.docx"
        assert data["Size"] == 12345
        assert data["OwnerId"] == "user1"
        assert data["UserFriendlyName"] == "Test User"
        assert data["UserCanWrite"] is True

    def test_session_expiry_uses_utc(self, app_with_wopi):
        """Verify session expiry comparison uses UTC correctly.

        This test ensures that a session created with UTC expiry time
        is correctly compared against current UTC time, not local time.
        """
        app, sessions_table, storages_table = app_with_wopi

        # Create a session that expires in 30 minutes UTC
        # This should be valid regardless of local timezone
        utc_now = _utcnow()
        expiry_utc = utc_now + timedelta(minutes=30)

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": expiry_utc.isoformat(),
            "tenant_id": "default",
            "storage_name": "HOME",
            "file_path": "/test.docx",
            "account": "user1",
            "user": "User",
        })

        # Mock storage
        mock_node = MagicMock()
        mock_node.exists = AsyncMock(return_value=True)
        mock_node.size = AsyncMock(return_value=100)
        mock_node.basename = "test.docx"
        mock_node.mtime = AsyncMock(return_value=1700000000.0)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        # Should be valid (not expired)
        assert response.status_code == 200

    def test_file_not_in_storage_returns_404(self, app_with_wopi):
        """CheckFileInfo returns 404 when file doesn't exist in storage."""
        app, sessions_table, storages_table = app_with_wopi

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": (_utcnow() + timedelta(hours=1)).isoformat(),
            "tenant_id": "acme",
            "storage_name": "HOME",
            "file_path": "/missing.docx",
            "account": "user1",
        })

        mock_node = MagicMock()
        mock_node.exists = AsyncMock(return_value=False)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found in storage"


class TestWopiGetFile:
    """Tests for WOPI GetFile endpoint."""

    def test_get_file_returns_content(self, app_with_wopi):
        """GetFile returns file content as binary."""
        app, sessions_table, storages_table = app_with_wopi

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "tenant_id": "acme",
            "storage_name": "HOME",
            "file_path": "/test.docx",
        })

        file_content = b"PK\x03\x04..." * 100  # Fake docx content
        mock_node = MagicMock()
        mock_node.exists = AsyncMock(return_value=True)
        mock_node.is_file = AsyncMock(return_value=True)
        mock_node.read_bytes = AsyncMock(return_value=file_content)
        mock_node.mtime = AsyncMock(return_value=1700000000.0)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        client = TestClient(app)
        response = client.get("/wopi/files/file123/contents?access_token=token123")

        assert response.status_code == 200
        assert response.content == file_content
        assert response.headers["content-type"] == "application/octet-stream"
        assert "X-WOPI-ItemVersion" in response.headers

    def test_get_file_invalid_token(self, app_with_wopi):
        """GetFile returns 401 for invalid token."""
        app, sessions_table, _ = app_with_wopi

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "correct_token",
        })

        client = TestClient(app)
        response = client.get("/wopi/files/file123/contents?access_token=wrong")

        assert response.status_code == 401


class TestWopiPutFile:
    """Tests for WOPI PutFile endpoint."""

    def test_put_file_saves_content(self, app_with_wopi):
        """PutFile saves content to storage."""
        app, sessions_table, storages_table = app_with_wopi

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "tenant_id": "acme",
            "storage_name": "HOME",
            "file_path": "/test.docx",
        })

        mock_node = MagicMock()
        mock_node.write_bytes = AsyncMock()
        mock_node.mtime = AsyncMock(return_value=1700000001.0)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        new_content = b"Updated document content"

        client = TestClient(app)
        response = client.post(
            "/wopi/files/file123/contents?access_token=token123",
            content=new_content,
        )

        assert response.status_code == 200
        assert "ItemVersion" in response.json()
        mock_node.write_bytes.assert_called_once_with(new_content)

    def test_put_file_invalid_token(self, app_with_wopi):
        """PutFile returns 401 for invalid token."""
        app, sessions_table, _ = app_with_wopi

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "correct_token",
        })

        client = TestClient(app)
        response = client.post(
            "/wopi/files/file123/contents?access_token=wrong",
            content=b"data",
        )

        assert response.status_code == 401


class TestUtcDatetimeHandling:
    """Tests specifically for UTC datetime handling.

    These tests ensure consistent UTC handling across the codebase.
    """

    def test_session_expiry_boundary(self, app_with_wopi):
        """Test session expiry at exact boundary."""
        app, sessions_table, storages_table = app_with_wopi

        # Session expires exactly now - should be expired
        utc_now = _utcnow()
        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": utc_now.isoformat(),
        })

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_session_expiry_one_second_future(self, app_with_wopi):
        """Test session expiring 1 second in future - should be valid."""
        app, sessions_table, storages_table = app_with_wopi

        utc_now = _utcnow()
        expiry = utc_now + timedelta(seconds=10)  # 10 seconds buffer for test execution

        sessions_table.get_by_file_id = AsyncMock(return_value={
            "access_token": "token123",
            "expires_at": expiry.isoformat(),
            "tenant_id": "default",
            "storage_name": "HOME",
            "file_path": "/test.docx",
            "account": "user1",
        })

        mock_node = MagicMock()
        mock_node.exists = AsyncMock(return_value=True)
        mock_node.size = AsyncMock(return_value=100)
        mock_node.basename = "test.docx"
        mock_node.mtime = AsyncMock(return_value=1700000000.0)

        mock_manager = MagicMock()
        mock_manager.node = MagicMock(return_value=mock_node)
        storages_table.get_storage_manager = AsyncMock(return_value=mock_manager)

        client = TestClient(app)
        response = client.get("/wopi/files/file123?access_token=token123")

        assert response.status_code == 200
