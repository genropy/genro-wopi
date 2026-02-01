# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Configuration dataclasses for WopiServer (Community Edition).

This module defines the configuration hierarchy for genro-wopi.
WopiConfig is the single entry point for all configuration, organizing
settings into logical nested groups.

Architecture:
    WopiConfig is used by WopiServerBase (and thus WopiProxy) to configure
    the service. It is CE-only: Enterprise Edition does not extend these
    dataclasses but rather stores EE-specific config in the database.

Usage:
    config = WopiConfig(
        db_path="/data/wopi.db",
        default_wopi_client_url="https://collabora.softwell.it",
    )
    wopi = WopiProxy(config=config)

    # Access config
    ttl = wopi.config.wopi_token_ttl
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WopiConfig:
    """Main configuration container for WopiServer (CE).

    Single entry point for all WOPI server configuration.

    Top-Level Settings:
        db_path: SQLite/PostgreSQL database path
        instance_name: Service identifier for display
        port: Default API server port
        api_token: Optional bearer token for API auth
        default_wopi_client_url: Pool WOPI client server URL
        wopi_token_ttl: WOPI access token TTL in seconds
        test_mode: Disable auto-processing for tests
        start_active: Start processing immediately

    Example:
        config = WopiConfig(
            db_path="/data/wopi.db",
            default_wopi_client_url="https://collabora.softwell.it",
            wopi_token_ttl=3600,
        )
        wopi = WopiProxy(config=config)
    """

    db_path: str = "/data/wopi_server.db"
    """SQLite database path for persistence."""

    instance_name: str = "wopi-server"
    """Instance name for display and identification."""

    port: int = 8000
    """Default port for API server."""

    api_token: str | None = None
    """API authentication token. If None, no auth required."""

    default_wopi_client_url: str = "https://collabora.softwell.it"
    """Default WOPI client server URL (Softwell pool). Can be Collabora, OnlyOffice, etc."""

    wopi_token_ttl: int = 3600
    """WOPI access token time-to-live in seconds (default 1 hour)."""

    test_mode: bool = False
    """Enable test mode (disables automatic processing)."""

    start_active: bool = False
    """Whether to start processing immediately."""


__all__ = ["WopiConfig"]
