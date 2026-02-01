# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Command log entity module.

This module provides the CommandLog entity for maintaining an audit
trail of all state-modifying API commands in the WOPI server.

Components:
    CommandLogTable: Database table manager for log storage.
    CommandLogEndpoint: REST API endpoint for querying logs.

Use Cases:
    - Debugging: Trace command history to diagnose issues
    - Migration: Export and replay commands on new instances
    - Recovery: Rebuild state from command history
    - Compliance: Maintain audit trail for regulations

Example:
    Access via WopiServerBase::

        from core.wopi_server.wopi_base import WopiServerBase

        wopi = WopiServerBase(db_path=":memory:")
        await wopi.init()

        # Log a command
        log = wopi.db.table("command_log")
        await log.log_command(
            endpoint="POST /tenant",
            payload={"id": "acme", "name": "Acme Corp"},
            tenant_id="acme",
        )

        # Query via endpoint
        from core.wopi_server.entities.command_log import CommandLogEndpoint
        endpoint = CommandLogEndpoint(log)
        commands = await endpoint.list(tenant_id="acme")
"""

from .endpoint import CommandLogEndpoint
from .table import CommandLogTable

__all__ = ["CommandLogEndpoint", "CommandLogTable"]
