# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""genro-wopi: WOPI implementation for the Genropy framework.

This package provides the core WOPI (Web Application Open Platform Interface)
implementation for the Genropy framework. Supports Collabora Online, OnlyOffice,
Microsoft 365, and other WOPI-compatible editors.

Main components:
    WopiConfig: Configuration dataclass
    WopiProxy: Main proxy with WOPI protocol handlers
    wopi_config_from_env: Factory to build config from environment

Usage:
    from genro_wopi import WopiProxy, WopiConfig

    config = WopiConfig(
        db_path="/data/wopi.db",
        default_wopi_client_url="https://collabora.softwell.it",
    )
    proxy = WopiProxy(config=config)
    app = proxy.api.app  # FastAPI application
"""

__version__ = "0.1.1"

from .wopi_proxy import WopiConfig, WopiProxy, wopi_config_from_env

__all__ = [
    "WopiConfig",
    "WopiProxy",
    "wopi_config_from_env",
    "main",
]


def main() -> None:
    """CLI entry point. Creates a WopiProxy and runs the CLI."""
    proxy = WopiProxy()
    proxy.cli()()
