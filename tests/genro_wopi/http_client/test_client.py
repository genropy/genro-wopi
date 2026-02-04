# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for WOPI HTTP client.

Tests cover connection registry, dataclasses, and WopiProxyClient
with mocked HTTP responses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from genro_wopi.http_client.client import (
    Storage,
    StoragesAPI,
    Tenant,
    TenantsAPI,
    WopiProxyClient,
    _connections,
    connect,
    register_connection,
)


class TestConnectionRegistry:
    """Tests for connection registry functions."""

    def setup_method(self):
        """Clear registry before each test."""
        _connections.clear()

    def test_register_connection(self):
        """register_connection saves connection info."""
        register_connection("prod", "https://wopi.example.com", token="secret")

        assert "prod" in _connections
        assert _connections["prod"]["url"] == "https://wopi.example.com"
        assert _connections["prod"]["token"] == "secret"

    def test_register_connection_without_token(self):
        """register_connection works without token."""
        register_connection("local", "http://localhost:8000")

        assert _connections["local"]["token"] is None

    def test_connect_with_url(self):
        """connect with URL creates client directly."""
        client = connect("http://localhost:8000", token="mytoken")

        assert isinstance(client, WopiProxyClient)
        assert client.base_url == "http://localhost:8000"
        assert client.token == "mytoken"

    def test_connect_with_registered_name(self):
        """connect with registered name uses stored config."""
        register_connection("staging", "https://staging.example.com", token="staging-key")

        client = connect("staging")

        assert client.base_url == "https://staging.example.com"
        assert client.token == "staging-key"

    def test_connect_ignores_token_for_registered(self):
        """connect ignores token parameter when using registered connection."""
        register_connection("prod", "https://prod.example.com", token="prod-key")

        client = connect("prod", token="ignored")

        assert client.token == "prod-key"


class TestTenantDataclass:
    """Tests for Tenant dataclass."""

    def test_tenant_from_dict_minimal(self):
        """Tenant.from_dict with minimal fields."""
        data = {"id": "acme"}
        tenant = Tenant.from_dict(data)

        assert tenant.id == "acme"
        assert tenant.name is None
        assert tenant.wopi_mode == "pool"
        assert tenant.active is True

    def test_tenant_from_dict_full(self):
        """Tenant.from_dict with all fields."""
        data = {
            "id": "bigcorp",
            "name": "Big Corp",
            "wopi_mode": "own",
            "wopi_client_url": "https://collabora.bigcorp.com",
            "active": False,
        }
        tenant = Tenant.from_dict(data)

        assert tenant.id == "bigcorp"
        assert tenant.name == "Big Corp"
        assert tenant.wopi_mode == "own"
        assert tenant.wopi_client_url == "https://collabora.bigcorp.com"
        assert tenant.active is False

    def test_tenant_from_dict_extra_fields(self):
        """Tenant.from_dict captures extra fields."""
        data = {
            "id": "test",
            "name": "Test",
            "custom_field": "value",
            "another": 123,
        }
        tenant = Tenant.from_dict(data)

        assert tenant.extra == {"custom_field": "value", "another": 123}


class TestStorageDataclass:
    """Tests for Storage dataclass."""

    def test_storage_from_dict(self):
        """Storage.from_dict parses all fields."""
        data = {
            "pk": "tenant1:s3",
            "tenant_id": "tenant1",
            "name": "s3",
            "protocol": "s3",
            "config": {"bucket": "mybucket"},
        }
        storage = Storage.from_dict(data)

        assert storage.pk == "tenant1:s3"
        assert storage.tenant_id == "tenant1"
        assert storage.name == "s3"
        assert storage.protocol == "s3"
        assert storage.config == {"bucket": "mybucket"}

    def test_storage_from_dict_no_config(self):
        """Storage.from_dict handles missing config."""
        data = {
            "pk": "tenant1:local",
            "tenant_id": "tenant1",
            "name": "local",
            "protocol": "file",
        }
        storage = Storage.from_dict(data)

        assert storage.config == {}


class TestWopiProxyClient:
    """Tests for WopiProxyClient."""

    def test_client_init(self):
        """WopiProxyClient initializes with base_url and token."""
        client = WopiProxyClient("http://localhost:8000/", token="secret")

        assert client.base_url == "http://localhost:8000"  # trailing slash stripped
        assert client.token == "secret"
        assert isinstance(client.tenants, TenantsAPI)
        assert isinstance(client.storages, StoragesAPI)

    def test_client_headers_with_token(self):
        """_headers includes X-API-Token when token is set."""
        client = WopiProxyClient("http://localhost:8000", token="mytoken")

        headers = client._headers()

        assert headers == {"X-API-Token": "mytoken"}

    def test_client_headers_without_token(self):
        """_headers returns empty dict when no token."""
        client = WopiProxyClient("http://localhost:8000")

        headers = client._headers()

        assert headers == {}


class TestWopiProxyClientRequests:
    """Tests for WopiProxyClient HTTP methods with mocks."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return WopiProxyClient("http://localhost:8000", token="test")

    async def test_status(self, client):
        """status calls /instance/status endpoint."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"ok": True, "active": True}

            result = await client.status()

            mock_get.assert_called_once_with("/instance/status")
            assert result == {"ok": True, "active": True}


class TestTenantsAPI:
    """Tests for TenantsAPI with mocks."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return WopiProxyClient("http://localhost:8000", token="test")

    async def test_tenants_list(self, client):
        """tenants.list returns list of Tenant objects."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "t1", "name": "Tenant 1"},
                {"id": "t2", "name": "Tenant 2"},
            ]

            result = await client.tenants.list()

            mock_get.assert_called_once()
            assert len(result) == 2
            assert all(isinstance(t, Tenant) for t in result)
            assert result[0].id == "t1"
            assert result[1].id == "t2"

    async def test_tenants_list_active_only(self, client):
        """tenants.list passes active_only parameter."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            await client.tenants.list(active_only=True)

            mock_get.assert_called_once_with(
                "/tenants/list", params={"active_only": "true"}
            )

    async def test_tenants_get(self, client):
        """tenants.get returns single Tenant."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"id": "acme", "name": "Acme Corp"}

            result = await client.tenants.get("acme")

            mock_get.assert_called_once_with(
                "/tenants/get", params={"tenant_id": "acme"}
            )
            assert isinstance(result, Tenant)
            assert result.id == "acme"

    async def test_tenants_add(self, client):
        """tenants.add creates tenant via POST."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": "new", "name": "New Corp", "wopi_mode": "own"}

            result = await client.tenants.add(
                id="new", name="New Corp", wopi_mode="own"
            )

            mock_post.assert_called_once()
            assert isinstance(result, Tenant)
            assert result.id == "new"
            assert result.wopi_mode == "own"

    async def test_tenants_delete_ok(self, client):
        """tenants.delete returns True on success."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"ok": True}

            result = await client.tenants.delete("old")

            mock_post.assert_called_once_with("/tenants/delete", {"tenant_id": "old"})
            assert result is True

    async def test_tenants_delete_true_result(self, client):
        """tenants.delete handles True result."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = True

            result = await client.tenants.delete("old")

            assert result is True


class TestStoragesAPI:
    """Tests for StoragesAPI with mocks."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return WopiProxyClient("http://localhost:8000", token="test")

    async def test_storages_list(self, client):
        """storages.list returns list of Storage objects."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"pk": "t1:s3", "tenant_id": "t1", "name": "s3", "protocol": "s3"},
            ]

            result = await client.storages.list("t1")

            mock_get.assert_called_once_with(
                "/storages/list", params={"tenant_id": "t1"}
            )
            assert len(result) == 1
            assert isinstance(result[0], Storage)

    async def test_storages_get(self, client):
        """storages.get returns single Storage."""
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "pk": "t1:local",
                "tenant_id": "t1",
                "name": "local",
                "protocol": "file",
            }

            result = await client.storages.get("t1", "local")

            mock_get.assert_called_once_with(
                "/storages/get", params={"tenant_id": "t1", "name": "local"}
            )
            assert isinstance(result, Storage)
            assert result.name == "local"

    async def test_storages_add(self, client):
        """storages.add creates storage via POST."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "pk": "t1:new",
                "tenant_id": "t1",
                "name": "new",
                "protocol": "s3",
                "config": {"bucket": "test"},
            }

            result = await client.storages.add(
                tenant_id="t1", name="new", protocol="s3", config={"bucket": "test"}
            )

            mock_post.assert_called_once()
            assert isinstance(result, Storage)
            assert result.config == {"bucket": "test"}

    async def test_storages_add_no_config(self, client):
        """storages.add sends empty config dict when not provided."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "pk": "t1:simple",
                "tenant_id": "t1",
                "name": "simple",
                "protocol": "file",
            }

            await client.storages.add(tenant_id="t1", name="simple", protocol="file")

            call_args = mock_post.call_args
            assert call_args[0][1]["config"] == {}

    async def test_storages_delete_ok(self, client):
        """storages.delete returns True on success."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"ok": True}

            result = await client.storages.delete("t1", "old")

            mock_post.assert_called_once_with(
                "/storages/delete", {"tenant_id": "t1", "name": "old"}
            )
            assert result is True

    async def test_storages_delete_non_dict(self, client):
        """storages.delete handles non-dict result."""
        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = "unexpected"

            result = await client.storages.delete("t1", "old")

            assert result is False
