# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI Server: Document editing proxy for Collabora Online integration.

This package provides the core WOPI (Web Application Open Platform Interface)
implementation for the Genropy framework.

Main components:
    WopiConfig: Configuration dataclass
    WopiServerBase: Foundation class with database, tables, endpoints
    WopiProxy: Main proxy with WOPI protocol handlers

Usage:
    from core.wopi_server import WopiProxy, WopiConfig

    config = WopiConfig(
        db_path="/data/wopi.db",
        default_collabora_url="https://collabora.softwell.it",
    )
    proxy = WopiProxy(config=config)
    app = proxy.api  # FastAPI application
"""

from .wopi_base import WopiServerBase
from .wopi_config import WopiConfig
from .wopi_proxy import WopiProxy

# Check if Enterprise Edition is available
HAS_ENTERPRISE = False
try:
    import enterprise.wopi_server  # noqa: F401

    HAS_ENTERPRISE = True
except ImportError:
    pass

__all__ = [
    "HAS_ENTERPRISE",
    "WopiConfig",
    "WopiProxy",
    "WopiServerBase",
]
