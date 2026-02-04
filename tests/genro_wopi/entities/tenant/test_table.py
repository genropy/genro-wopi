# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for TenantsTable WOPI extension.

Tests cover WOPI-specific columns, default tenant creation,
and get_wopi_client_url logic for different modes.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from genro_wopi import WopiConfig, WopiProxy


@pytest_asyncio.fixture
async def server(tmp_path):
    """Create server with database and keep connection open during tests."""
    server = WopiProxy(WopiConfig(db_path=str(tmp_path / "test.db")))
    await server.init()
    async with server.db.connection():
        yield server
    await server.shutdown()


@pytest_asyncio.fixture
async def tenants_table(server):
    """Get tenants table from database."""
    return server.db.table("tenants")


class TestTenantsTableConfigure:
    """Tests for TenantsTable.configure()."""

    async def test_configure_adds_wopi_columns(self, tenants_table):
        """TenantsTable has wopi_mode and wopi_client_url columns."""
        columns = tenants_table.columns
        column_names = list(columns)  # Columns is iterable, yields names

        assert "wopi_mode" in column_names
        assert "wopi_client_url" in column_names


class TestEnsureDefault:
    """Tests for TenantsTable.ensure_default()."""

    async def test_ensure_default_creates_tenant(self, tenants_table):
        """ensure_default creates a 'default' tenant if missing."""
        # ensure_default is called during server.init()
        tenant = await tenants_table.record(where={"id": "default"})

        assert tenant is not None
        assert tenant["id"] == "default"
        assert tenant["name"] == "Default Tenant"
        assert tenant["active"] == 1

    async def test_ensure_default_idempotent(self, tenants_table):
        """Multiple ensure_default calls don't duplicate tenant."""
        # Call again
        await tenants_table.ensure_default()
        await tenants_table.ensure_default()

        # Count tenants with id='default'
        count = await tenants_table.db.count("tenants", where={"id": "default"})
        assert count == 1

    async def test_ensure_default_preserves_existing_name(self, tenants_table):
        """ensure_default doesn't overwrite existing tenant name."""
        # Update the default tenant name
        async with tenants_table.record_to_update("default") as rec:
            rec["name"] = "Custom Name"

        # Call ensure_default again
        await tenants_table.ensure_default()

        # Name should be preserved
        tenant = await tenants_table.record(where={"id": "default"})
        assert tenant["name"] == "Custom Name"


class TestGetWopiClientUrl:
    """Tests for TenantsTable.get_wopi_client_url()."""

    async def test_get_wopi_client_url_pool_mode(self, tenants_table):
        """Pool mode returns default URL."""
        # Create tenant with pool mode
        async with tenants_table.record_to_update("acme", insert_missing=True) as rec:
            rec["name"] = "Acme Corp"
            rec["wopi_mode"] = "pool"
            rec["active"] = 1

        url = await tenants_table.get_wopi_client_url(
            "acme", default_url="https://collabora.softwell.it"
        )

        assert url == "https://collabora.softwell.it"

    async def test_get_wopi_client_url_own_mode_with_url(self, tenants_table):
        """Own mode with custom URL returns tenant's URL."""
        async with tenants_table.record_to_update("bigcorp", insert_missing=True) as rec:
            rec["name"] = "Big Corp"
            rec["wopi_mode"] = "own"
            rec["wopi_client_url"] = "https://collabora.bigcorp.com"
            rec["active"] = 1

        url = await tenants_table.get_wopi_client_url(
            "bigcorp", default_url="https://collabora.softwell.it"
        )

        assert url == "https://collabora.bigcorp.com"

    async def test_get_wopi_client_url_own_mode_without_url(self, tenants_table):
        """Own mode without custom URL falls back to default."""
        async with tenants_table.record_to_update("noclient", insert_missing=True) as rec:
            rec["name"] = "No Client Corp"
            rec["wopi_mode"] = "own"
            # wopi_client_url not set
            rec["active"] = 1

        url = await tenants_table.get_wopi_client_url(
            "noclient", default_url="https://collabora.softwell.it"
        )

        assert url == "https://collabora.softwell.it"

    async def test_get_wopi_client_url_disabled(self, tenants_table):
        """Disabled mode returns None."""
        async with tenants_table.record_to_update("disabled_corp", insert_missing=True) as rec:
            rec["name"] = "Disabled Corp"
            rec["wopi_mode"] = "disabled"
            rec["active"] = 1

        url = await tenants_table.get_wopi_client_url(
            "disabled_corp", default_url="https://collabora.softwell.it"
        )

        assert url is None

    async def test_get_wopi_client_url_missing_tenant(self, tenants_table):
        """Missing tenant returns default URL."""
        url = await tenants_table.get_wopi_client_url(
            "nonexistent", default_url="https://collabora.softwell.it"
        )

        assert url == "https://collabora.softwell.it"

    async def test_get_wopi_client_url_no_mode_defaults_pool(self, tenants_table):
        """Tenant without wopi_mode defaults to pool behavior."""
        # Insert tenant without explicitly setting wopi_mode
        async with tenants_table.record_to_update("nomode", insert_missing=True) as rec:
            rec["name"] = "No Mode Corp"
            rec["active"] = 1
            # wopi_mode will use default "pool"

        url = await tenants_table.get_wopi_client_url(
            "nomode", default_url="https://collabora.softwell.it"
        )

        assert url == "https://collabora.softwell.it"
