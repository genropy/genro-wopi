# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI Session REST API endpoint.

This module provides the WopiSessionEndpoint class for managing WOPI editing
sessions via REST API and CLI commands.

Example:
    CLI commands auto-generated::

        wopi-server wopi-sessions list [--tenant-id TENANT]
        wopi-server wopi-sessions get --session-id SESSION_ID
        wopi-server wopi-sessions close --session-id SESSION_ID
        wopi-server wopi-sessions cleanup [--dry-run]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from genro_proxy.interface.endpoint_base import POST, BaseEndpoint

if TYPE_CHECKING:
    from .table import WopiSessionsTable


class WopiSessionEndpoint(BaseEndpoint):
    """REST API endpoint for WOPI session management.

    Provides operations for creating, listing, and managing WOPI sessions.

    Attributes:
        name: Endpoint name used in URL paths ("wopi_sessions").
        table: WopiSessionsTable instance for database operations.

    Example:
        Using the endpoint programmatically::

            endpoint = WopiSessionEndpoint(db.table("wopi_sessions"))

            # Create session
            session = await endpoint.create(
                storage_name="attachments",
                file_path="docs/report.xlsx",
                permissions=["view", "edit"],
                account="sales",
                user="Mario Rossi",
            )

            # List active sessions
            sessions = await endpoint.list()
    """

    name = "wopi_sessions"

    def __init__(self, table: WopiSessionsTable):
        """Initialize endpoint with table reference.

        Args:
            table: SessionsTable instance for database operations.
        """
        super().__init__(table)

    @POST
    async def create(
        self,
        storage_name: str,
        file_path: str,
        permissions: list[str],
        account: str,
        user: str | None = None,
        origin_connection_id: str | None = None,
        origin_page_id: str | None = None,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Create a new WOPI session.

        Args:
            storage_name: Storage backend name.
            file_path: Document path in storage.
            permissions: List of permissions (["view"] or ["view", "edit"]).
            account: Account for audit (required).
            user: User name (optional, for collaborative editing).
            origin_connection_id: Genropy connection ID for callbacks.
            origin_page_id: Genropy page context.
            ttl_seconds: Session TTL in seconds (default 3600).

        Returns:
            Session dict with session_id, file_id, access_token, expires_at.

        Note:
            The tenant_id is resolved from the authenticated request context.
            In CE mode, "default" tenant is used.
        """
        # tenant_id is resolved from request context (injected by WopiProxy)
        tenant_id = getattr(self, "_current_tenant_id", "default")

        return await self.table.create_session(
            tenant_id=tenant_id,
            storage_name=storage_name,
            file_path=file_path,
            permissions=permissions,
            account=account,
            user=user,
            origin_connection_id=origin_connection_id,
            origin_page_id=origin_page_id,
            ttl_seconds=ttl_seconds,
        )

    async def get(self, session_id: str) -> dict[str, Any]:
        """Retrieve a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session dict.

        Raises:
            ValueError: If session not found.
        """
        session = await self.table.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")
        return session

    async def list(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List active sessions.

        Args:
            tenant_id: Optional filter by tenant.

        Returns:
            List of active session dicts.
        """
        return await self.table.list_active(tenant_id=tenant_id)

    @POST
    async def close(self, session_id: str) -> bool:
        """Close a session early.

        Args:
            session_id: Session identifier.

        Returns:
            True if closed, False if not found.
        """
        return await self.table.remove(session_id)

    @POST
    async def cleanup(self, dry_run: bool = False) -> dict[str, Any]:
        """Remove expired sessions.

        Args:
            dry_run: If True, only count without deleting.

        Returns:
            Dict with 'deleted' count.
        """
        if dry_run:
            # Count expired sessions
            sessions = await self.table.select()
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            expired = [s for s in sessions if s.get("expires_at", "") <= now]
            return {"deleted": 0, "would_delete": len(expired)}

        deleted = await self.table.cleanup_expired()
        return {"deleted": deleted}


__all__ = ["WopiSessionEndpoint"]
