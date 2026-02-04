# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""WOPI Proxy: configuration, base class, and protocol implementation.

This module defines:
- WopiConfig: Configuration dataclass extending ProxyConfigBase
- wopi_config_from_env(): Factory to build config from WOPI_* env vars
- WopiProxy: Main WOPI proxy service class

Configuration via environment variables:
    WOPI_DB: Database path (SQLite file or PostgreSQL URL)
    WOPI_API_TOKEN: API authentication token
    WOPI_INSTANCE: Instance name for display
    WOPI_PORT: Server port (default: 8000)
    WOPI_CLIENT_URL: Default WOPI client URL (Collabora, OnlyOffice, etc.)
    WOPI_TOKEN_TTL: WOPI access token TTL in seconds

Discovery Mechanism:
    Tables from `genro_wopi.entities.*/table.py`.
    Endpoints follow the same pattern with `endpoint.py`.

    WOPI-specific entities:
        - tenants: Extends proxy TenantsTable with wopi_mode, wopi_client_url
        - wopi_sessions: WOPI editing sessions (100% WOPI-specific)

    Inherited from proxy (auto-discovered):
        - instance: Service-level configuration
        - storages: Per-tenant storage backends
        - command_log: API audit trail

Usage:
    from genro_wopi import WopiProxy, WopiConfig

    # From environment (Docker/production):
    config = wopi_config_from_env()
    proxy = WopiProxy(config=config)

    # Explicit configuration:
    config = WopiConfig(
        db_path="/data/wopi.db",
        default_wopi_client_url="https://collabora.softwell.it",
    )
    proxy = WopiProxy(config=config)

    # As FastAPI app
    app = proxy.api.app

    # Or run directly
    await proxy.start()
    # ... handle requests ...
    await proxy.stop()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from genro_proxy.proxy_base import ProxyBase, ProxyConfigBase

logger = logging.getLogger("genro_wopi")


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


@dataclass
class WopiConfig(ProxyConfigBase):
    """Configuration for WopiProxy service.

    Extends ProxyConfigBase with WOPI-specific settings.

    Inherited from ProxyConfigBase:
        db_path: SQLite/PostgreSQL database path
        instance_name: Service identifier for display
        port: Default API server port
        api_token: Optional bearer token for API auth
        test_mode: Disable auto-processing for tests
        start_active: Start processing immediately

    WOPI-Specific Settings:
        default_wopi_client_url: Pool WOPI client server URL
        wopi_token_ttl: WOPI access token TTL in seconds
    """

    default_wopi_client_url: str = "https://collabora.softwell.it"
    """Default WOPI client server URL (Softwell pool)."""

    wopi_token_ttl: int = 3600
    """WOPI access token time-to-live in seconds (default 1 hour)."""


def wopi_config_from_env() -> WopiConfig:
    """Build WopiConfig from WOPI_* environment variables.

    Environment variables:
        WOPI_DB: Database path (default: /data/wopi.db)
        WOPI_API_TOKEN: API token (default: None, no auth)
        WOPI_INSTANCE: Instance name (default: "wopi")
        WOPI_PORT: Server port (default: 8000)
        WOPI_CLIENT_URL: Default WOPI client URL
        WOPI_TOKEN_TTL: Token TTL in seconds (default: 3600)
        WOPI_TEST_MODE: Enable test mode (default: false)
        WOPI_START_ACTIVE: Start active (default: false)

    Returns:
        WopiConfig instance populated from environment.
    """
    return WopiConfig(
        db_path=os.environ.get("WOPI_DB", "/data/wopi.db"),
        instance_name=os.environ.get("WOPI_INSTANCE", "wopi"),
        port=int(os.environ.get("WOPI_PORT", "8000")),
        api_token=os.environ.get("WOPI_API_TOKEN"),
        test_mode=os.environ.get("WOPI_TEST_MODE", "").lower() in ("1", "true", "yes"),
        start_active=os.environ.get("WOPI_START_ACTIVE", "").lower()
        in ("1", "true", "yes"),
        default_wopi_client_url=os.environ.get(
            "WOPI_CLIENT_URL", "https://collabora.softwell.it"
        ),
        wopi_token_ttl=int(os.environ.get("WOPI_TOKEN_TTL", "3600")),
    )


# -----------------------------------------------------------------------------
# WopiProxy
# -----------------------------------------------------------------------------


class WopiProxy(ProxyBase):
    """WOPI protocol proxy service.

    Extends ProxyBase with WOPI-specific entity discovery and protocol
    implementation for document editing integration with WOPI-compatible
    clients (Collabora Online, OnlyOffice, Microsoft 365, etc.).

    Attributes:
        config: WopiConfig instance
        db: SqlDb instance with WOPI tables
        endpoints: EndpointManager with WOPI endpoints
        api: ApiManager (creates FastAPI app lazily)
        cli: CliManager (creates Click group lazily)

    WOPI Protocol (to be implemented):
        - CheckFileInfo: Return file metadata
        - GetFile: Download file content
        - PutFile: Save edited file
        - Lock/Unlock: Collaborative editing locks
    """

    entity_packages: list[str] = ["genro_wopi.entities"]
    encryption_key_env: str = "WOPI_ENCRYPTION_KEY"

    def __init__(self, config: WopiConfig | None = None):
        """Initialize WopiProxy.

        Args:
            config: WopiConfig instance. If None, creates default.
        """
        super().__init__(config or WopiConfig())
        self._active = False

    async def init(self) -> None:
        """Initialize database and WOPI-specific setup.

        Extends ProxyBase.init() with default tenant creation.
        """
        await super().init()

        # Ensure default tenant exists
        async with self.db.connection():
            tenants_table = self.db.table("tenants")
            await tenants_table.ensure_default()

        logger.info("WopiProxy initialized")

    async def start(self) -> None:
        """Start the WOPI proxy service.

        Initializes database and begins accepting requests.
        """
        await self.init()
        self._active = True
        logger.info(f"WopiProxy '{self.config.instance_name}' started")

    async def stop(self) -> None:
        """Stop the WOPI proxy service.

        Closes database connection and cleans up resources.
        """
        self._active = False
        await self.shutdown()
        logger.info(f"WopiProxy '{self.config.instance_name}' stopped")

    # -------------------------------------------------------------------------
    # WOPI Protocol handlers (stubs - to be implemented)
    # -------------------------------------------------------------------------

    async def check_file_info(self, file_id: str, access_token: str) -> dict:
        """WOPI CheckFileInfo: Return file metadata.

        Args:
            file_id: Unique file identifier.
            access_token: WOPI access token for authorization.

        Returns:
            File info dict per WOPI spec (BaseFileName, Size, OwnerId, etc.)

        TODO: Implement in future phase.
        """
        raise NotImplementedError("WOPI CheckFileInfo not yet implemented")

    async def get_file(self, file_id: str, access_token: str) -> bytes:
        """WOPI GetFile: Download file content.

        Args:
            file_id: Unique file identifier.
            access_token: WOPI access token for authorization.

        Returns:
            File content as bytes.

        TODO: Implement in future phase.
        """
        raise NotImplementedError("WOPI GetFile not yet implemented")

    async def put_file(
        self, file_id: str, access_token: str, content: bytes
    ) -> dict:
        """WOPI PutFile: Save edited file.

        Args:
            file_id: Unique file identifier.
            access_token: WOPI access token for authorization.
            content: New file content.

        Returns:
            Status dict per WOPI spec.

        TODO: Implement in future phase.
        """
        raise NotImplementedError("WOPI PutFile not yet implemented")


__all__ = ["WopiConfig", "WopiProxy", "wopi_config_from_env"]
