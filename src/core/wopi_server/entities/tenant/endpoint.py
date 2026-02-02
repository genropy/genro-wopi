# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tenant REST API endpoint.

This module provides the TenantEndpoint class exposing CRUD operations
for tenant configurations via REST API and CLI commands.

Example:
    CLI commands auto-generated::

        wopi-server tenants add --id acme --name "Acme Corp"
        wopi-server tenants list
        wopi-server tenants get --tenant-id acme
        wopi-server tenants delete --tenant-id acme
        wopi-server tenants update --tenant-id acme --wopi-mode own --wopi-client-url https://...
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from ...interface.endpoint_base import POST, BaseEndpoint

if TYPE_CHECKING:
    from .table import TenantsTable


class WopiMode(str, Enum):
    """WOPI mode for tenant configuration.

    Attributes:
        POOL: Use Softwell shared WOPI client pool.
        OWN: Use tenant's own WOPI client server.
        DISABLED: WOPI editing disabled for this tenant.
    """

    POOL = "pool"
    OWN = "own"
    DISABLED = "disabled"


class TenantEndpoint(BaseEndpoint):
    """REST API endpoint for tenant management.

    Provides CRUD operations for tenant configurations.

    Attributes:
        name: Endpoint name used in URL paths ("tenants").
        table: TenantsTable instance for database operations.

    Example:
        Using the endpoint programmatically::

            endpoint = TenantEndpoint(db.table("tenants"))

            # Add tenant
            tenant = await endpoint.add(
                id="acme",
                name="Acme Corp",
                wopi_mode="own",
                wopi_client_url="https://collabora.acme.com",
            )

            # List tenants
            tenants = await endpoint.list()
    """

    name = "tenants"

    def __init__(self, table: TenantsTable):
        """Initialize endpoint with table reference.

        Args:
            table: TenantsTable instance for database operations.
        """
        super().__init__(table)

    @POST
    async def add(
        self,
        id: str,
        name: str | None = None,
        wopi_mode: str = "pool",
        wopi_client_url: str | None = None,
        client_auth: dict[str, Any] | None = None,
        client_base_url: str | None = None,
        active: bool = True,
    ) -> dict:
        """Add or update a tenant configuration.

        Args:
            id: Tenant identifier (unique).
            name: Human-readable tenant name.
            wopi_mode: WOPI mode ("pool", "own", "disabled"). Default "pool".
            wopi_client_url: Custom WOPI client URL when wopi_mode="own".
            client_auth: HTTP auth config for callbacks.
            client_base_url: Base URL for client HTTP callbacks.
            active: Whether tenant is active.

        Returns:
            Tenant dict.
        """
        data = {k: v for k, v in locals().items() if k != "self"}
        # Convert bool to int for database storage
        data["active"] = 1 if active else 0
        await self.table.add(data)
        tenant = await self.table.get(id)
        return tenant

    async def get(self, tenant_id: str) -> dict:
        """Retrieve a single tenant configuration.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            Tenant configuration dict.

        Raises:
            ValueError: If tenant not found.
        """
        tenant = await self.table.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        return tenant

    async def list(self, active_only: bool = False) -> list[dict]:
        """List all tenants.

        Args:
            active_only: If True, only return active tenants.

        Returns:
            List of tenant configuration dicts.
        """
        return await self.table.list_all(active_only=active_only)

    @POST
    async def delete(self, tenant_id: str) -> bool:
        """Delete a tenant.

        Args:
            tenant_id: Tenant identifier to delete.

        Returns:
            True if deleted.
        """
        return await self.table.remove(tenant_id)

    @POST
    async def update(
        self,
        tenant_id: str,
        name: str | None = None,
        wopi_mode: str | None = None,
        wopi_client_url: str | None = None,
        client_auth: dict[str, Any] | None = None,
        client_base_url: str | None = None,
        active: bool | None = None,
    ) -> dict:
        """Update tenant configuration fields.

        Only provided fields are updated; None values are ignored.

        Args:
            tenant_id: Tenant identifier.
            name: New tenant name.
            wopi_mode: New WOPI mode.
            wopi_client_url: New WOPI client URL.
            client_auth: New auth config.
            client_base_url: New base URL.
            active: New active status.

        Returns:
            Updated tenant configuration dict.
        """
        fields = {
            k: v for k, v in locals().items() if k not in ("self", "tenant_id") and v is not None
        }
        # Convert bool to int for database storage
        if "active" in fields:
            fields["active"] = 1 if fields["active"] else 0
        await self.table.update_fields(tenant_id, fields)
        return await self.table.get(tenant_id)

    # -------------------------------------------------------------------------
    # API Key Management
    # -------------------------------------------------------------------------

    @POST
    async def create_api_key(
        self,
        tenant_id: str,
        expires_at: int | None = None,
    ) -> dict:
        """Create a new API key for a tenant.

        Generates a new random API key, replacing any existing key.
        The raw key is returned once and cannot be retrieved later.
        Save it immediately!

        Args:
            tenant_id: The tenant ID.
            expires_at: Optional Unix timestamp for key expiration.

        Returns:
            Dict with ok=True and api_key (show once).

        Raises:
            ValueError: If tenant not found.
        """
        api_key = await self.table.create_api_key(tenant_id, expires_at)
        if api_key is None:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "api_key": api_key,
            "message": "Save this API key - it will not be shown again.",
        }

    @POST
    async def revoke_api_key(self, tenant_id: str) -> dict:
        """Revoke the API key for a tenant.

        Removes the API key, preventing further authentication with it.
        The tenant can still be accessed via instance token.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Dict with ok=True.

        Raises:
            ValueError: If tenant not found.
        """
        success = await self.table.revoke_api_key(tenant_id)
        if not success:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        return {"ok": True, "tenant_id": tenant_id, "message": "API key revoked"}


__all__ = ["TenantEndpoint", "WopiMode"]
