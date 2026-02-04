# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""ASGI application entry point for uvicorn.

This module provides the FastAPI application instance for deployment
with ASGI servers like uvicorn, hypercorn, or gunicorn+uvicorn.

Configuration via environment variables:
    WOPI_DB: Database path (SQLite file or PostgreSQL URL)
    WOPI_API_TOKEN: API authentication token
    WOPI_INSTANCE: Instance name for display
    WOPI_PORT: Server port (default: 8000)
    WOPI_CLIENT_URL: Default WOPI client URL

Example:
    Run with uvicorn::

        WOPI_DB=/data/wopi.db WOPI_API_TOKEN=secret \\
            uvicorn genro_wopi.server:app --host 0.0.0.0 --port 8000

    Run with Docker::

        docker run -e WOPI_DB=/data/wopi.db -e WOPI_API_TOKEN=secret ...

    Or via CLI::

        wopi-server serve --port 8000

Note:
    The application includes a lifespan context manager that calls
    proxy.start() on startup and proxy.stop() on shutdown, ensuring
    proper initialization and graceful cleanup.
"""

from .wopi_proxy import WopiProxy, wopi_config_from_env

# Create proxy and expose its FastAPI app (includes lifespan management)
_proxy = WopiProxy(config=wopi_config_from_env())
app = _proxy.api.app
