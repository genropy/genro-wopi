# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for TenantEndpoint WOPI extension.

Tests cover WOPI-specific add/update methods, API key management,
and WopiMode enum.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from genro_wopi import WopiConfig, WopiProxy
from genro_wopi.entities.tenant.endpoint import TenantEndpoint, WopiMode


@pytest_asyncio.fixture
async def server(tmp_path):
    """Create server with database and keep connection open during tests."""
    server = WopiProxy(WopiConfig(db_path=str(tmp_path / "test.db")))
    await server.init()
    async with server.db.connection():
        yield server
    await server.shutdown()


@pytest_asyncio.fixture
async def tenant_endpoint(server) -> TenantEndpoint:
    """Get tenant endpoint from server."""
    return server.endpoints._endpoints["tenants"]


class TestWopiModeEnum:
    """Tests for WopiMode enum."""

    def test_wopi_mode_values(self):
        """WopiMode has correct values."""
        assert WopiMode.POOL.value == "pool"
        assert WopiMode.OWN.value == "own"
        assert WopiMode.DISABLED.value == "disabled"

    def test_wopi_mode_is_string_enum(self):
        """WopiMode inherits from str."""
        assert isinstance(WopiMode.POOL, str)
        assert WopiMode.POOL == "pool"


class TestTenantEndpointAdd:
    """Tests for TenantEndpoint.add()."""

    async def test_add_tenant_basic(self, tenant_endpoint):
        """Add tenant with minimal fields."""
        result = await tenant_endpoint.add(id="acme", name="Acme Corp")

        assert result["id"] == "acme"
        assert result["name"] == "Acme Corp"
        assert result["active"] == 1
        assert result["wopi_mode"] == "pool"  # default

    async def test_add_tenant_wopi_fields(self, tenant_endpoint):
        """Add tenant with WOPI-specific fields."""
        result = await tenant_endpoint.add(
            id="bigcorp",
            name="Big Corp",
            wopi_mode="own",
            wopi_client_url="https://collabora.bigcorp.com",
        )

        assert result["id"] == "bigcorp"
        assert result["wopi_mode"] == "own"
        assert result["wopi_client_url"] == "https://collabora.bigcorp.com"

    async def test_add_tenant_disabled_mode(self, tenant_endpoint):
        """Add tenant with WOPI disabled."""
        result = await tenant_endpoint.add(
            id="nowopi",
            name="No WOPI Corp",
            wopi_mode="disabled",
        )

        assert result["wopi_mode"] == "disabled"

    async def test_add_tenant_inactive(self, tenant_endpoint):
        """Add inactive tenant."""
        result = await tenant_endpoint.add(
            id="inactive",
            name="Inactive Corp",
            active=False,
        )

        assert result["active"] == 0

    async def test_add_tenant_upsert(self, tenant_endpoint):
        """Add updates existing tenant (upsert behavior)."""
        # First add
        await tenant_endpoint.add(id="upsert", name="Original Name")

        # Second add updates
        result = await tenant_endpoint.add(id="upsert", name="Updated Name")

        assert result["name"] == "Updated Name"

    async def test_add_tenant_with_config(self, tenant_endpoint):
        """Add tenant with custom config."""
        result = await tenant_endpoint.add(
            id="configured",
            name="Configured Corp",
            config={"max_file_size": 100_000_000},
        )

        assert result["config"]["max_file_size"] == 100_000_000


class TestTenantEndpointUpdate:
    """Tests for TenantEndpoint.update()."""

    async def test_update_tenant_name(self, tenant_endpoint):
        """Update only tenant name."""
        await tenant_endpoint.add(id="updateme", name="Original")

        result = await tenant_endpoint.update(tenant_id="updateme", name="New Name")

        assert result["name"] == "New Name"
        assert result["wopi_mode"] == "pool"  # unchanged

    async def test_update_tenant_wopi_mode(self, tenant_endpoint):
        """Update WOPI mode."""
        await tenant_endpoint.add(id="modechange", name="Mode Corp", wopi_mode="pool")

        result = await tenant_endpoint.update(tenant_id="modechange", wopi_mode="own")

        assert result["wopi_mode"] == "own"

    async def test_update_tenant_wopi_client_url(self, tenant_endpoint):
        """Update WOPI client URL."""
        await tenant_endpoint.add(id="urlchange", name="URL Corp", wopi_mode="own")

        result = await tenant_endpoint.update(
            tenant_id="urlchange",
            wopi_client_url="https://new-collabora.example.com",
        )

        assert result["wopi_client_url"] == "https://new-collabora.example.com"

    async def test_update_tenant_partial(self, tenant_endpoint):
        """Update only specified fields, others unchanged."""
        await tenant_endpoint.add(
            id="partial",
            name="Partial Corp",
            wopi_mode="own",
            wopi_client_url="https://old.url.com",
        )

        # Update only name
        result = await tenant_endpoint.update(tenant_id="partial", name="New Partial")

        assert result["name"] == "New Partial"
        assert result["wopi_mode"] == "own"  # unchanged
        assert result["wopi_client_url"] == "https://old.url.com"  # unchanged

    async def test_update_tenant_active_status(self, tenant_endpoint):
        """Update active status."""
        await tenant_endpoint.add(id="toggle", name="Toggle Corp", active=True)

        result = await tenant_endpoint.update(tenant_id="toggle", active=False)

        assert result["active"] == 0


class TestTenantEndpointApiKey:
    """Tests for API key management methods."""

    async def test_create_api_key(self, tenant_endpoint):
        """Create API key for tenant."""
        await tenant_endpoint.add(id="apikey", name="API Key Corp")

        result = await tenant_endpoint.create_api_key(tenant_id="apikey")

        assert result["ok"] is True
        assert result["tenant_id"] == "apikey"
        assert "api_key" in result
        assert len(result["api_key"]) > 0
        assert "message" in result

    async def test_create_api_key_with_expiration(self, tenant_endpoint):
        """Create API key with expiration."""
        await tenant_endpoint.add(id="expiring", name="Expiring Corp")

        result = await tenant_endpoint.create_api_key(
            tenant_id="expiring",
            expires_at=1735689600,  # Some future timestamp
        )

        assert result["ok"] is True
        assert "api_key" in result

    async def test_create_api_key_not_found(self, tenant_endpoint):
        """Create API key for nonexistent tenant raises error."""
        with pytest.raises(Exception, match="not found"):
            await tenant_endpoint.create_api_key(tenant_id="nonexistent")

    @pytest.mark.skip(reason="revoke_api_key not implemented in TenantsTable")
    async def test_revoke_api_key(self, tenant_endpoint):
        """Revoke API key for tenant."""
        await tenant_endpoint.add(id="revoke", name="Revoke Corp")
        await tenant_endpoint.create_api_key(tenant_id="revoke")

        result = await tenant_endpoint.revoke_api_key(tenant_id="revoke")

        assert result["ok"] is True
        assert result["tenant_id"] == "revoke"
        assert "message" in result

    @pytest.mark.skip(reason="revoke_api_key not implemented in TenantsTable")
    async def test_revoke_api_key_not_found(self, tenant_endpoint):
        """Revoke API key for nonexistent tenant raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await tenant_endpoint.revoke_api_key(tenant_id="nonexistent")
