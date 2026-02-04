# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI server entity modules.

This package contains WOPI-specific database entities:
    - tenant: Multi-tenant configurations (extends proxy with WOPI fields)
    - wopi_session: WOPI editing sessions

Base entities (instance, storage, command_log) are provided by genro-proxy.
"""

from .tenant import TenantEndpoint, TenantsTable, WopiMode
from .wopi_session import WopiSessionEndpoint, WopiSessionsTable

__all__ = [
    "TenantEndpoint",
    "TenantsTable",
    "WopiMode",
    "WopiSessionEndpoint",
    "WopiSessionsTable",
]
