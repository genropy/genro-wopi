# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Instance REST API endpoint for service-level operations.

This module provides the InstanceEndpoint class exposing service-level
operations for the WOPI server via REST API and CLI commands.

Operations include:
    - health: Container orchestration health check (unauthenticated)
    - status: Authenticated service status
    - get/update: Instance configuration management

Example:
    CLI commands auto-generated::

        wopi-server instance health
        wopi-server instance status
        wopi-server instance get
        wopi-server instance update --name production
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...interface.endpoint_base import POST, BaseEndpoint

if TYPE_CHECKING:
    from .table import InstanceTable


class InstanceEndpoint(BaseEndpoint):
    """REST API endpoint for instance-level operations.

    Provides service management operations including health checks
    and configuration management.

    Attributes:
        name: Endpoint name used in URL paths ("instance").
        table: InstanceTable instance for configuration storage.
        proxy: Optional WopiProxy instance for service operations.

    Example:
        Using the endpoint programmatically::

            endpoint = InstanceEndpoint(db.table("instance"), proxy)

            # Check service health
            health = await endpoint.health()

            # Update configuration
            await endpoint.update(name="production")
    """

    name = "instance"

    def __init__(self, table: InstanceTable, proxy: object | None = None):
        """Initialize endpoint with table and optional proxy reference.

        Args:
            table: InstanceTable for configuration storage.
            proxy: Optional WopiProxy instance for service operations.
        """
        super().__init__(table)
        self.proxy = proxy

    async def health(self) -> dict:
        """Health check for container orchestration.

        Lightweight endpoint for liveness/readiness probes. Does not
        require authentication. Returns immediately without database access.

        Returns:
            Dict with status "ok".

        Example:
            ::

                # Kubernetes liveness probe
                # GET /instance/health
                {"status": "ok"}
        """
        return {"status": "ok"}

    async def status(self) -> dict:
        """Authenticated service status.

        Returns the current active state of the WOPI server service.
        Requires authentication.

        Returns:
            Dict with ok=True and active boolean indicating if
            the service is running.
        """
        active = True
        if self.proxy is not None:
            active = getattr(self.proxy, "_active", True)
        return {"ok": True, "active": active}

    async def get(self) -> dict:
        """Get instance configuration.

        Returns:
            Dict with ok=True and all instance configuration fields.
        """
        instance = await self.table.get_instance()
        if instance is None:
            return {"ok": True, "id": 1, "name": "wopi-server", "edition": "ce"}
        return {"ok": True, **instance}

    @POST
    async def update(
        self,
        name: str | None = None,
        api_token: str | None = None,
        edition: str | None = None,
    ) -> dict:
        """Update instance configuration.

        Args:
            name: New instance display name.
            api_token: New master API token.
            edition: New edition ("ce" or "ee").

        Returns:
            Dict with ok=True.
        """
        updates = {}
        if name is not None:
            updates["name"] = name
        if api_token is not None:
            updates["api_token"] = api_token
        if edition is not None:
            updates["edition"] = edition

        if updates:
            await self.table.update_instance(updates)
        return {"ok": True}


__all__ = ["InstanceEndpoint"]
