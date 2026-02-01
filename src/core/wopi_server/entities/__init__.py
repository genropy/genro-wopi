# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI server entity modules.

This package contains all database entities for the WOPI server:
    - instance: Singleton service configuration
    - tenant: Multi-tenant configurations
    - storage: Per-tenant storage backends
    - command_log: API audit trail
"""

from .command_log import CommandLogEndpoint, CommandLogTable
from .instance import InstanceEndpoint, InstanceTable
from .storage import StorageEndpoint, StoragesTable
from .tenant import TenantEndpoint, TenantsTable

__all__ = [
    "CommandLogEndpoint",
    "CommandLogTable",
    "InstanceEndpoint",
    "InstanceTable",
    "StorageEndpoint",
    "StoragesTable",
    "TenantEndpoint",
    "TenantsTable",
]
