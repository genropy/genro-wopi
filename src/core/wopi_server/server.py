# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""ASGI application entry point for uvicorn.

This module provides the FastAPI application instance for deployment
with ASGI servers like uvicorn, hypercorn, or gunicorn+uvicorn.

Components:
    app: FastAPI application with full WopiProxy lifecycle management.
    _proxy: Internal WopiProxy instance (use app instead).

Example:
    Run with uvicorn::

        uvicorn core.wopi_server.server:app --host 0.0.0.0 --port 8000

    Run with reload for development::

        uvicorn core.wopi_server.server:app --reload

    Or via CLI::

        wopi-proxy serve --port 8000

Note:
    The application includes a lifespan context manager that calls
    proxy.start() on startup and proxy.stop() on shutdown, ensuring
    proper initialization and graceful cleanup.
"""

from .wopi_proxy import WopiProxy

# Create proxy and expose its API (includes lifespan management)
_proxy = WopiProxy()
app = _proxy.api
