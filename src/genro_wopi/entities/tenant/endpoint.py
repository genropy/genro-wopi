# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI Tenant REST API endpoint.

Extends proxy TenantEndpoint with WOPI-specific fields (wopi_mode, wopi_client_url)
and API key management methods.

Example:
    CLI commands auto-generated::

        wopi-server tenants add --id acme --name "Acme Corp" --wopi-mode own
        wopi-server tenants update --tenant-id acme --wopi-client-url https://...
        wopi-server tenants create-api-key --tenant-id acme
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from genro_proxy.entities.tenant.endpoint import TenantEndpoint as ProxyTenantEndpoint
from genro_proxy.interface.endpoint_base import POST

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


class TenantEndpoint(ProxyTenantEndpoint):
    """WOPI tenant endpoint extending proxy with WOPI-specific fields.

    Adds:
        - wopi_mode, wopi_client_url parameters to add() and update()
        - create_api_key(), revoke_api_key() methods
    """

    def __init__(self, table: TenantsTable):
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
        config: dict[str, Any] | None = None,
        active: bool = True,
    ) -> dict:
        """Add or update a tenant with WOPI-specific fields.

        Args:
            id: Tenant identifier (unique).
            name: Human-readable tenant name.
            wopi_mode: WOPI mode ("pool", "own", "disabled"). Default "pool".
            wopi_client_url: Custom WOPI client URL when wopi_mode="own".
            client_auth: HTTP auth config for callbacks.
            client_base_url: Base URL for client HTTP callbacks.
            config: Additional tenant-specific configuration.
            active: Whether tenant is active.

        Returns:
            Tenant dict.
        """
        async with self.table.record_to_update(id, insert_missing=True) as rec:
            if name is not None:
                rec["name"] = name
            if client_auth is not None:
                rec["client_auth"] = client_auth
            if client_base_url is not None:
                rec["client_base_url"] = client_base_url
            if config is not None:
                rec["config"] = config
            rec["active"] = 1 if active else 0
            # WOPI-specific fields
            rec["wopi_mode"] = wopi_mode
            if wopi_client_url is not None:
                rec["wopi_client_url"] = wopi_client_url

        return await self.get(id)

    @POST
    async def update(
        self,
        tenant_id: str,
        name: str | None = None,
        wopi_mode: str | None = None,
        wopi_client_url: str | None = None,
        client_auth: dict[str, Any] | None = None,
        client_base_url: str | None = None,
        config: dict[str, Any] | None = None,
        active: bool | None = None,
    ) -> dict:
        """Update tenant with WOPI-specific fields.

        Only provided fields are updated; None values are ignored.

        Args:
            tenant_id: Tenant identifier.
            name: New tenant name.
            wopi_mode: New WOPI mode.
            wopi_client_url: New WOPI client URL.
            client_auth: New auth config.
            client_base_url: New base URL.
            config: New config dict.
            active: New active status.

        Returns:
            Updated tenant configuration dict.
        """
        async with self.table.record_to_update(tenant_id) as rec:
            if name is not None:
                rec["name"] = name
            if client_auth is not None:
                rec["client_auth"] = client_auth
            if client_base_url is not None:
                rec["client_base_url"] = client_base_url
            if config is not None:
                rec["config"] = config
            if active is not None:
                rec["active"] = 1 if active else 0
            # WOPI-specific fields
            if wopi_mode is not None:
                rec["wopi_mode"] = wopi_mode
            if wopi_client_url is not None:
                rec["wopi_client_url"] = wopi_client_url

        return await self.get(tenant_id)

    @POST
    async def revoke_api_key(self, tenant_id: str) -> dict:
        """Revoke the API key for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Dict with ok=True.
        """
        success = await self.table.revoke_api_key(tenant_id)
        if not success:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        return {"ok": True, "tenant_id": tenant_id, "message": "API key revoked"}


__all__ = ["TenantEndpoint", "WopiMode"]
