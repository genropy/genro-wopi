# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI session entity: editing session management."""

from .endpoint import WopiSessionEndpoint
from .table import WopiSessionsTable

__all__ = ["WopiSessionEndpoint", "WopiSessionsTable"]
