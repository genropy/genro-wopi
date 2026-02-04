# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI-specific tenant table extending proxy TenantsTable.

Adds WOPI-specific columns:
    - wopi_mode: "pool" (Softwell shared), "own" (custom server), "disabled"
    - wopi_client_url: Custom WOPI client URL when wopi_mode="own"
"""

from __future__ import annotations

from genro_proxy.entities.tenant.table import TenantsTable as ProxyTenantsTable
from genro_proxy.sql import String


class TenantsTable(ProxyTenantsTable):
    """WOPI tenant table with WOPI-specific columns.

    Extends proxy TenantsTable adding:
        - wopi_mode: WOPI client mode (pool/own/disabled)
        - wopi_client_url: Custom WOPI client URL for wopi_mode="own"
    """

    def configure(self) -> None:
        """Define columns: proxy base + WOPI-specific."""
        super().configure()
        c = self.columns
        c.column("wopi_mode", String, default="pool")  # pool, own, disabled
        c.column("wopi_client_url", String)  # Custom WOPI client URL

    async def ensure_default(self) -> None:
        """Ensure the 'default' tenant exists for CE single-tenant mode."""
        async with self.record_to_update("default", insert_missing=True) as rec:
            if not rec.get("name"):
                rec["name"] = "Default Tenant"
                rec["active"] = 1
                rec["wopi_mode"] = "pool"

    async def get_wopi_client_url(self, tenant_id: str, default_url: str) -> str | None:
        """Get effective WOPI client URL for a tenant.

        Args:
            tenant_id: Tenant identifier.
            default_url: Pool WOPI client URL (Softwell shared).

        Returns:
            WOPI client URL to use, or None if WOPI is disabled.
        """
        tenant = await self.record(where={"id": tenant_id}, ignore_missing=True)
        if not tenant:
            return default_url

        mode = tenant.get("wopi_mode", "pool")
        if mode == "disabled":
            return None
        elif mode == "own":
            return tenant.get("wopi_client_url") or default_url
        else:  # pool
            return default_url


__all__ = ["TenantsTable"]
