# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Development server for testing with docker-compose environment.

Starts the WOPI server configured for the demo environment:
- PostgreSQL on localhost:5433
- MinIO on localhost:9002
- Collabora on localhost:9980

Usage:
    python run_server.py
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Configure for demo environment
os.environ.setdefault("WOPI_DB_PATH", "postgresql://wopi:wopi@localhost:5433/wopi")


def main():
    """Start the WOPI server."""
    import uvicorn

    from core.wopi_server.wopi_config import WopiConfig
    from core.wopi_server.wopi_proxy import WopiProxy

    config = WopiConfig(
        db_path="postgresql://wopi:wopi@localhost:5433/wopi",
        port=8080,
    )
    proxy = WopiProxy(config=config)
    app = proxy.api

    print("Starting WOPI server on http://localhost:8080")
    print("Demo client: http://localhost:3000")
    print("MinIO console: http://localhost:9003 (minioadmin/minioadmin)")
    print("Collabora: http://localhost:9980")

    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
