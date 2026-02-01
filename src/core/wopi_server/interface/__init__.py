# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Interface layer for API and CLI.

This package provides infrastructure for exposing WopiServer functionality
through multiple interfaces using introspection-based route/command generation.

Components:
    BaseEndpoint: Base class for all endpoint definitions.
    create_app: FastAPI application factory.
    register_api_endpoint: Register endpoint as FastAPI routes.
    register_cli_endpoint: Register endpoint as Click commands.

Example:
    Create a FastAPI application::

        from core.wopi_server.interface import create_app
        from core.wopi_server.wopi_proxy import WopiProxy

        proxy = WopiProxy(db_path="/data/wopi.db")
        app = create_app(proxy, api_token="secret")

    Register CLI commands::

        import click
        from core.wopi_server.interface import register_cli_endpoint

        @click.group()
        def cli():
            pass

        endpoint = TenantEndpoint(table)
        register_cli_endpoint(cli, endpoint)

Note:
    All interfaces are generated dynamically from endpoint class
    method signatures via introspection. No hardcoded routes or
    commands required.
"""

from .api_base import create_app
from .api_base import register_endpoint as register_api_endpoint
from .cli_base import register_endpoint as register_cli_endpoint
from .endpoint_base import POST, BaseEndpoint

__all__ = [
    "BaseEndpoint",
    "POST",
    "create_app",
    "register_api_endpoint",
    "register_cli_endpoint",
]
