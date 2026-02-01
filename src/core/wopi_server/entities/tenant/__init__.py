# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tenant entity: multi-tenant configuration table and endpoint."""

from .endpoint import TenantEndpoint, WopiMode
from .table import TenantsTable

__all__ = ["TenantEndpoint", "TenantsTable", "WopiMode"]
