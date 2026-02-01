# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""HTTP client for WOPI server API.

This module provides WopiProxyClient for programmatic access to WOPI
server endpoints, with support for both sync and async contexts.

Features:
    - Auto-detects sync/async context (via @smartasync)
    - Persistent connection registration for REPL use
    - Typed dataclasses for Tenant, Storage responses
    - Token-based authentication

Example:
    Async usage::

        async with httpx.AsyncClient() as http:
            client = WopiProxyClient("http://localhost:8000", token="secret")
            status = await client.status()
            tenants = await client.tenants.list()

    Sync usage (in REPL)::

        client = connect("http://localhost:8000", token="secret")
        status = client.status()
        tenants = client.tenants.list()

    Registered connection::

        register_connection("prod", "https://wopi.example.com", token="...")
        client = connect("prod")  # Uses registered URL/token
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from genro_toolbox import smartasync

# Connection registry for REPL convenience
_connections: dict[str, dict[str, Any]] = {}


def register_connection(name: str, url: str, token: str | None = None) -> None:
    """Register a named connection for easy reuse.

    Args:
        name: Connection name for later reference.
        url: WOPI server base URL.
        token: Optional API token.

    Example:
        >>> register_connection("prod", "https://wopi.prod.example.com", token="secret")
        >>> client = connect("prod")
    """
    _connections[name] = {"url": url, "token": token}


def connect(url_or_name: str, token: str | None = None) -> WopiProxyClient:
    """Create a WopiProxyClient, optionally using a registered connection.

    Args:
        url_or_name: Either a URL or a registered connection name.
        token: API token (ignored if using registered connection).

    Returns:
        WopiProxyClient instance.

    Example:
        >>> client = connect("http://localhost:8000", token="secret")
        >>> # or with registered connection:
        >>> client = connect("prod")
    """
    if url_or_name in _connections:
        conn = _connections[url_or_name]
        return WopiProxyClient(conn["url"], token=conn["token"])
    return WopiProxyClient(url_or_name, token=token)


@dataclass
class Tenant:
    """Tenant configuration response."""

    id: str
    name: str | None = None
    wopi_mode: str = "pool"
    wopi_client_url: str | None = None
    active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tenant:
        """Create Tenant from API response dict."""
        known = {"id", "name", "wopi_mode", "wopi_client_url", "active"}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            id=data["id"],
            name=data.get("name"),
            wopi_mode=data.get("wopi_mode", "pool"),
            wopi_client_url=data.get("wopi_client_url"),
            active=data.get("active", True),
            extra=extra,
        )


@dataclass
class Storage:
    """Storage backend configuration response."""

    pk: str
    tenant_id: str
    name: str
    protocol: str
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Storage:
        """Create Storage from API response dict."""
        return cls(
            pk=data["pk"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            protocol=data["protocol"],
            config=data.get("config", {}),
        )


class TenantsAPI:
    """Tenants endpoint API wrapper."""

    def __init__(self, client: WopiProxyClient):
        self._client = client

    @smartasync
    async def list(self, active_only: bool = False) -> list[Tenant]:
        """List all tenants."""
        params = {"active_only": str(active_only).lower()}
        data = await self._client._get("/tenants/list", params=params)
        return [Tenant.from_dict(t) for t in data]

    @smartasync
    async def get(self, tenant_id: str) -> Tenant:
        """Get a specific tenant."""
        data = await self._client._get("/tenants/get", params={"tenant_id": tenant_id})
        return Tenant.from_dict(data)

    @smartasync
    async def add(
        self,
        id: str,
        name: str | None = None,
        wopi_mode: str = "pool",
        wopi_client_url: str | None = None,
        active: bool = True,
    ) -> Tenant:
        """Add or update a tenant."""
        payload = {
            "id": id,
            "name": name,
            "wopi_mode": wopi_mode,
            "wopi_client_url": wopi_client_url,
            "active": active,
        }
        data = await self._client._post("/tenants/add", payload)
        return Tenant.from_dict(data)

    @smartasync
    async def delete(self, tenant_id: str) -> bool:
        """Delete a tenant."""
        result = await self._client._post("/tenants/delete", {"tenant_id": tenant_id})
        return result is True or (isinstance(result, dict) and result.get("ok", False))


class StoragesAPI:
    """Storages endpoint API wrapper."""

    def __init__(self, client: WopiProxyClient):
        self._client = client

    @smartasync
    async def list(self, tenant_id: str) -> list[Storage]:
        """List storage backends for a tenant."""
        data = await self._client._get("/storages/list", params={"tenant_id": tenant_id})
        return [Storage.from_dict(s) for s in data]

    @smartasync
    async def get(self, tenant_id: str, name: str) -> Storage:
        """Get a specific storage backend."""
        data = await self._client._get(
            "/storages/get", params={"tenant_id": tenant_id, "name": name}
        )
        return Storage.from_dict(data)

    @smartasync
    async def add(
        self,
        tenant_id: str,
        name: str,
        protocol: str,
        config: dict[str, Any] | None = None,
    ) -> Storage:
        """Add or update a storage backend."""
        payload = {
            "tenant_id": tenant_id,
            "name": name,
            "protocol": protocol,
            "config": config or {},
        }
        data = await self._client._post("/storages/add", payload)
        return Storage.from_dict(data)

    @smartasync
    async def delete(self, tenant_id: str, name: str) -> bool:
        """Delete a storage backend."""
        result = await self._client._post(
            "/storages/delete", {"tenant_id": tenant_id, "name": name}
        )
        return result.get("ok", False) if isinstance(result, dict) else False


class WopiProxyClient:
    """HTTP client for WOPI server API.

    Provides convenient access to all WOPI server endpoints with
    automatic sync/async context detection.

    Attributes:
        tenants: TenantsAPI for tenant management
        storages: StoragesAPI for storage backend management

    Example:
        >>> client = WopiProxyClient("http://localhost:8000", token="secret")
        >>> status = await client.status()
        >>> tenants = await client.tenants.list()
    """

    def __init__(self, base_url: str, token: str | None = None):
        """Initialize client.

        Args:
            base_url: WOPI server base URL.
            token: Optional API token for authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.token = token

        # Sub-APIs
        self.tenants = TenantsAPI(self)
        self.storages = StoragesAPI(self)

    def _headers(self) -> dict[str, str]:
        """Build request headers with optional auth token."""
        headers: dict[str, str] = {}
        if self.token:
            headers["X-API-Token"] = self.token
        return headers

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform GET request."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        """Perform POST request."""
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @smartasync
    async def status(self) -> dict[str, Any]:
        """Get service status.

        Returns:
            Dict with 'ok' and 'active' status.
        """
        return await self._get("/instance/status")

    @smartasync
    async def health(self) -> dict[str, Any]:
        """Health check (unauthenticated).

        Returns:
            Dict with 'status': 'ok'.
        """
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()


__all__ = [
    "Storage",
    "StoragesAPI",
    "Tenant",
    "TenantsAPI",
    "WopiProxyClient",
    "connect",
    "register_connection",
]
