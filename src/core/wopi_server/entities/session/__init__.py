# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Session entity: WOPI editing session management."""

from .endpoint import SessionEndpoint
from .table import SessionsTable

__all__ = ["SessionEndpoint", "SessionsTable"]
