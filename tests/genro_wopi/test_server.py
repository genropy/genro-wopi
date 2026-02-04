# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for server module (ASGI entry point)."""

from __future__ import annotations

from fastapi import FastAPI


class TestServerModule:
    """Tests for server module."""

    def test_app_is_fastapi(self):
        """app is a FastAPI instance."""
        from genro_wopi.server import app

        assert isinstance(app, FastAPI)

    def test_proxy_created(self):
        """_proxy is created from environment config."""
        from genro_wopi.server import _proxy
        from genro_wopi.wopi_proxy import WopiProxy

        assert isinstance(_proxy, WopiProxy)

    def test_app_is_proxy_api_app(self):
        """app is the proxy's API app."""
        from genro_wopi.server import _proxy, app

        assert app is _proxy.api.app
