# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tenant configuration table manager.

This module provides the TenantsTable class for managing tenant
configurations in a multi-tenant WOPI server environment.

Each tenant can configure:
    - WOPI client mode: pool (Softwell shared), own (customer server), disabled
    - Custom WOPI client URL (for mode="own")
    - Client authentication (for callbacks)
    - API key for tenant-scoped authentication

Example:
    Basic tenant operations::

        from core.wopi_server.wopi_base import WopiServerBase

        wopi = WopiServerBase(db_path=":memory:")
        await wopi.init()

        tenants = wopi.db.table("tenants")

        # Create tenant with API key
        api_key = await tenants.create_api_key("acme")

        # Get tenant by API key
        tenant = await tenants.get_tenant_by_token(api_key)
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from sql import Integer, String, Table, Timestamp


class TenantsTable(Table):
    """Tenant configuration storage table.

    Manages tenant settings including WOPI mode and WOPI client configuration.

    Attributes:
        name: Table name ("tenants").
        pkey: Primary key column ("id").

    Table Schema:
        - id: Tenant identifier (primary key)
        - name: Display name
        - wopi_mode: "pool" (Softwell shared), "own" (custom server), "disabled"
        - wopi_client_url: Custom WOPI client URL when wopi_mode="own"
        - client_auth: JSON dict with HTTP auth config for callbacks
        - client_base_url: Base URL for client callbacks
        - active: 0/1 flag for tenant status
        - api_key_hash: Hashed API key (EE only)
        - api_key_expires_at: API key expiration (EE only)
        - created_at, updated_at: Timestamps

    Example:
        Work with tenant configuration::

            tenants = wopi.db.table("tenants")

            # Get tenant
            tenant = await tenants.get("acme")

            # Check WOPI mode
            if tenant["wopi_mode"] == "own":
                wopi_client_url = tenant["wopi_client_url"]
    """

    name = "tenants"
    pkey = "id"

    def configure(self) -> None:
        """Define table columns.

        Columns:
            id: Tenant identifier (primary key string).
            name: Human-readable tenant name.
            wopi_mode: WOPI mode ("pool", "own", "disabled"). Default "pool".
            wopi_client_url: Custom WOPI client URL (for wopi_mode="own").
            client_auth: JSON dict with auth method, credentials for callbacks.
            client_base_url: Base URL for client HTTP callbacks.
            active: 1=active, 0=disabled (INTEGER for SQLite).
            api_key_hash: Bcrypt hash of API key (EE only).
            api_key_expires_at: API key expiration timestamp (EE only).
            created_at: Row creation timestamp.
            updated_at: Last modification timestamp.
        """
        c = self.columns
        c.column("id", String)
        c.column("name", String)
        c.column("wopi_mode", String, default="pool")  # pool, own, disabled
        c.column("wopi_client_url", String)  # Custom WOPI client URL for wopi_mode="own"
        c.column("client_auth", String, json_encoded=True)
        c.column("client_base_url", String)
        c.column("active", Integer, default=1)
        c.column("api_key_hash", String)
        c.column("api_key_expires_at", Timestamp)
        c.column("created_at", Timestamp, default="CURRENT_TIMESTAMP")
        c.column("updated_at", Timestamp, default="CURRENT_TIMESTAMP")

    async def get(self, tenant_id: str) -> dict[str, Any] | None:
        """Fetch a tenant configuration by ID.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            Tenant dict with 'active' converted to bool, or None if not found.
        """
        tenant = await self.select_one(where={"id": tenant_id})
        if not tenant:
            return None
        return self._decode_active(tenant)

    def _decode_active(self, tenant: dict[str, Any]) -> dict[str, Any]:
        """Convert active INTEGER to bool.

        Args:
            tenant: Raw tenant dict from database.

        Returns:
            Tenant dict with 'active' as boolean.
        """
        tenant["active"] = bool(tenant.get("active", 1))
        return tenant

    async def ensure_default(self) -> None:
        """Ensure the 'default' tenant exists for CE single-tenant mode.

        Creates the default tenant without API key. In CE mode, all
        operations use the instance token.
        """
        async with self.record("default", insert_missing=True) as rec:
            if not rec.get("name"):
                rec["name"] = "Default Tenant"
                rec["active"] = 1
                rec["wopi_mode"] = "pool"

    async def list_all(self, active_only: bool = False) -> list[dict[str, Any]]:
        """List all tenants.

        Args:
            active_only: If True, only return active tenants.

        Returns:
            List of tenant dicts.
        """
        if active_only:
            rows = await self.select(where={"active": 1}, order_by="id")
        else:
            rows = await self.select(order_by="id")
        return [self._decode_active(r) for r in rows]

    async def add(self, data: dict[str, Any]) -> str | None:
        """Add or update a tenant.

        Args:
            data: Tenant data dict with at least 'id'.

        Returns:
            API key if newly created (EE), else None.
        """
        tenant_id = data.get("id")
        if not tenant_id:
            raise ValueError("Tenant id is required")

        async with self.record(tenant_id, insert_missing=True) as rec:
            for key, value in data.items():
                if key != "id" and value is not None:
                    rec[key] = value

        return None  # API key generation is EE-only

    async def update_fields(self, tenant_id: str, fields: dict[str, Any]) -> None:
        """Update specific fields of a tenant.

        Args:
            tenant_id: Tenant identifier.
            fields: Dict of field names to new values.
        """
        async with self.record(tenant_id) as rec:
            if not rec:
                raise ValueError(f"Tenant '{tenant_id}' not found")
            for key, value in fields.items():
                rec[key] = value

    async def remove(self, tenant_id: str) -> bool:
        """Delete a tenant.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            True if deleted, False if not found.
        """
        result = await self.delete(where={"id": tenant_id})
        return result > 0

    async def get_wopi_client_url(self, tenant_id: str, default_url: str) -> str | None:
        """Get effective WOPI client URL for a tenant.

        Args:
            tenant_id: Tenant identifier.
            default_url: Pool WOPI client URL (Softwell shared).

        Returns:
            WOPI client URL to use, or None if WOPI is disabled.
        """
        tenant = await self.get(tenant_id)
        if not tenant:
            return default_url

        mode = tenant.get("wopi_mode", "pool")
        if mode == "disabled":
            return None
        elif mode == "own":
            return tenant.get("wopi_client_url") or default_url
        else:  # pool
            return default_url

    # -------------------------------------------------------------------------
    # API Key Management
    # -------------------------------------------------------------------------

    async def create_api_key(self, tenant_id: str, expires_at: int | None = None) -> str | None:
        """Create a new API key for a tenant.

        Generates a new random API key, replacing any existing key.
        The raw key is returned once and cannot be retrieved later.

        Args:
            tenant_id: The tenant ID.
            expires_at: Optional Unix timestamp for key expiration.

        Returns:
            The raw API key (show once), or None if tenant not found.
        """
        tenant = await self.get(tenant_id)
        if not tenant:
            return None

        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        await self.db.adapter.execute(
            """
            UPDATE tenants
            SET api_key_hash = :key_hash,
                api_key_expires_at = :expires_at,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :tenant_id
            """,
            {"tenant_id": tenant_id, "key_hash": key_hash, "expires_at": expires_at},
        )
        return raw_key

    async def get_tenant_by_token(self, raw_key: str) -> dict[str, Any] | None:
        """Find tenant by API key token.

        Looks up the tenant associated with the given API key.
        Validates that the key has not expired.

        Args:
            raw_key: The raw API key to look up.

        Returns:
            Tenant dict if found and not expired, None otherwise.
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        tenant = await self.db.adapter.fetch_one(
            "SELECT * FROM tenants WHERE api_key_hash = :key_hash",
            {"key_hash": key_hash},
        )
        if not tenant:
            return None

        expires_at = tenant.get("api_key_expires_at")
        if expires_at:
            # Handle both datetime (PostgreSQL) and int (SQLite) types
            if isinstance(expires_at, datetime):
                now = datetime.now(timezone.utc)
                # Make expires_at timezone-aware if it isn't
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now:
                    return None  # Expired
            else:
                # SQLite returns int (Unix timestamp)
                now_ts = datetime.now(timezone.utc).timestamp()
                if expires_at < now_ts:
                    return None  # Expired

        return self._decode_active(tenant)

    async def revoke_api_key(self, tenant_id: str) -> bool:
        """Revoke the API key for a tenant.

        Removes the API key, preventing further authentication.
        The tenant can still be accessed via instance token.

        Args:
            tenant_id: The tenant ID.

        Returns:
            True if key was revoked, False if tenant not found.
        """
        rowcount = await self.db.adapter.execute(
            """
            UPDATE tenants
            SET api_key_hash = NULL,
                api_key_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :tenant_id
            """,
            {"tenant_id": tenant_id},
        )
        return rowcount > 0


__all__ = ["TenantsTable"]
