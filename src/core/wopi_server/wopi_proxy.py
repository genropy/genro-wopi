# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Main WopiProxy class: WOPI protocol implementation.

WopiProxy extends WopiServerBase with WOPI protocol handlers
for document editing integration with Collabora Online.

This is a stub implementation - the actual WOPI protocol handlers
will be implemented in future development phases.

Usage:
    from core.wopi_server.wopi_proxy import WopiProxy
    from core.wopi_server.wopi_config import WopiConfig

    config = WopiConfig(
        db_path="/data/wopi.db",
        default_collabora_url="https://collabora.softwell.it",
    )
    proxy = WopiProxy(config=config)

    # As FastAPI app
    app = proxy.api

    # Or run directly
    await proxy.start()
    # ... handle requests ...
    await proxy.stop()
"""

from __future__ import annotations

import logging

from .wopi_base import WopiServerBase
from .wopi_config import WopiConfig

logger = logging.getLogger(__name__)


class WopiProxy(WopiServerBase):
    """WOPI protocol proxy service.

    Extends WopiServerBase with WOPI protocol implementation for
    document editing integration with Collabora Online.

    Attributes:
        config: WopiConfig instance
        db: SqlDb instance
        endpoints: Dict of endpoint instances

    WOPI Protocol (to be implemented):
        - CheckFileInfo: Return file metadata
        - GetFile: Download file content
        - PutFile: Save edited file
        - Lock/Unlock: Collaborative editing locks
    """

    def __init__(self, config: WopiConfig | None = None):
        """Initialize WopiProxy.

        Args:
            config: WopiConfig instance. If None, creates default.
        """
        super().__init__(config)
        self._active = False

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
        await self.close()
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

    async def put_file(self, file_id: str, access_token: str, content: bytes) -> dict:
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


__all__ = ["WopiProxy"]
