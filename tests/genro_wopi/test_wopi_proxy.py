# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Tests for WopiProxy, WopiConfig, and wopi_config_from_env.

Tests cover configuration defaults, environment variable parsing,
proxy initialization, lifecycle, and WOPI protocol stubs.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest
import pytest_asyncio

from genro_wopi import WopiConfig, WopiProxy, wopi_config_from_env


class TestWopiConfig:
    """Tests for WopiConfig dataclass."""

    def test_config_defaults(self):
        """WopiConfig has correct default values."""
        config = WopiConfig()

        # Inherited from ProxyConfigBase
        assert config.db_path == "/data/service.db"
        assert config.instance_name == "proxy"
        assert config.port == 8000
        assert config.api_token is None
        assert config.test_mode is False
        assert config.start_active is False

        # WOPI-specific
        assert config.default_wopi_client_url == "https://collabora.softwell.it"
        assert config.wopi_token_ttl == 3600

    def test_config_custom_values(self):
        """WopiConfig accepts custom values."""
        config = WopiConfig(
            db_path="/data/wopi.db",
            instance_name="wopi-prod",
            port=9000,
            api_token="secret123",
            test_mode=True,
            start_active=True,
            default_wopi_client_url="https://onlyoffice.example.com",
            wopi_token_ttl=7200,
        )

        assert config.db_path == "/data/wopi.db"
        assert config.instance_name == "wopi-prod"
        assert config.port == 9000
        assert config.api_token == "secret123"
        assert config.test_mode is True
        assert config.start_active is True
        assert config.default_wopi_client_url == "https://onlyoffice.example.com"
        assert config.wopi_token_ttl == 7200


class TestWopiConfigFromEnv:
    """Tests for wopi_config_from_env factory function."""

    def test_config_from_env_defaults(self):
        """With no env vars, uses defaults."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = wopi_config_from_env()

        assert config.db_path == "/data/wopi.db"
        assert config.instance_name == "wopi"
        assert config.port == 8000
        assert config.api_token is None
        assert config.test_mode is False
        assert config.start_active is False
        assert config.default_wopi_client_url == "https://collabora.softwell.it"
        assert config.wopi_token_ttl == 3600

    def test_config_from_env_custom(self):
        """Reads custom values from WOPI_* env vars."""
        env = {
            "WOPI_DB": "/custom/path.db",
            "WOPI_INSTANCE": "wopi-staging",
            "WOPI_PORT": "9090",
            "WOPI_API_TOKEN": "my-secret-token",
            "WOPI_CLIENT_URL": "https://collabora.custom.com",
            "WOPI_TOKEN_TTL": "1800",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = wopi_config_from_env()

        assert config.db_path == "/custom/path.db"
        assert config.instance_name == "wopi-staging"
        assert config.port == 9090
        assert config.api_token == "my-secret-token"
        assert config.default_wopi_client_url == "https://collabora.custom.com"
        assert config.wopi_token_ttl == 1800

    @pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "Yes"])
    def test_config_from_env_boolean_true(self, value):
        """Boolean env vars parsed correctly for truthy values."""
        env = {"WOPI_TEST_MODE": value, "WOPI_START_ACTIVE": value}
        with mock.patch.dict(os.environ, env, clear=True):
            config = wopi_config_from_env()

        assert config.test_mode is True
        assert config.start_active is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "", "other"])
    def test_config_from_env_boolean_false(self, value):
        """Boolean env vars parsed correctly for falsy values."""
        env = {"WOPI_TEST_MODE": value, "WOPI_START_ACTIVE": value}
        with mock.patch.dict(os.environ, env, clear=True):
            config = wopi_config_from_env()

        assert config.test_mode is False
        assert config.start_active is False


class TestWopiProxyInit:
    """Tests for WopiProxy initialization."""

    def test_proxy_init_default_config(self):
        """WopiProxy initializes with default config when none provided."""
        proxy = WopiProxy()

        assert proxy.config is not None
        assert isinstance(proxy.config, WopiConfig)

    def test_proxy_init_custom_config(self, tmp_path):
        """WopiProxy initializes with custom config."""
        config = WopiConfig(
            db_path=str(tmp_path / "test.db"),
            instance_name="test-wopi",
        )
        proxy = WopiProxy(config=config)

        assert proxy.config is config
        assert proxy.config.instance_name == "test-wopi"

    def test_proxy_entity_packages(self):
        """WopiProxy has correct entity_packages for discovery."""
        proxy = WopiProxy()

        assert "genro_wopi.entities" in proxy.entity_packages

    def test_proxy_encryption_key_env(self):
        """WopiProxy uses correct encryption key env var name."""
        proxy = WopiProxy()

        assert proxy.encryption_key_env == "WOPI_ENCRYPTION_KEY"


class TestWopiProxyLifecycle:
    """Tests for WopiProxy start/stop lifecycle."""

    @pytest_asyncio.fixture
    async def proxy(self, tmp_path):
        """Create a proxy with temporary database."""
        config = WopiConfig(db_path=str(tmp_path / "test.db"))
        proxy = WopiProxy(config=config)
        yield proxy
        # Cleanup if not already stopped
        if proxy._active:
            await proxy.stop()

    async def test_proxy_start_stop(self, proxy):
        """WopiProxy start() and stop() work correctly."""
        assert proxy._active is False

        await proxy.start()
        assert proxy._active is True

        await proxy.stop()
        assert proxy._active is False

    async def test_proxy_init_creates_default_tenant(self, proxy):
        """WopiProxy.init() creates default tenant."""
        await proxy.init()

        async with proxy.db.connection():
            tenants_table = proxy.db.table("tenants")
            tenant = await tenants_table.record(where={"id": "default"})

        assert tenant is not None
        assert tenant["name"] == "Default Tenant"
        # wopi_mode is stored in the record
        assert tenant.get("wopi_mode", "pool") == "pool"

    async def test_proxy_entity_discovery(self, proxy):
        """WopiProxy discovers WOPI entities (tables and endpoints)."""
        await proxy.init()

        # Check tables are discovered
        assert proxy.db.table("tenants") is not None
        assert proxy.db.table("wopi_sessions") is not None

        # Check endpoints are registered
        assert "tenants" in proxy.endpoints._endpoints
        assert "wopi_sessions" in proxy.endpoints._endpoints


class TestWopiProtocolStubs:
    """Tests for WOPI protocol handler stubs."""

    @pytest_asyncio.fixture
    async def proxy(self, tmp_path):
        """Create and initialize a proxy."""
        config = WopiConfig(db_path=str(tmp_path / "test.db"))
        proxy = WopiProxy(config=config)
        await proxy.init()
        yield proxy
        await proxy.shutdown()

    async def test_check_file_info_not_implemented(self, proxy):
        """check_file_info raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="CheckFileInfo"):
            await proxy.check_file_info("file_123", "token_abc")

    async def test_get_file_not_implemented(self, proxy):
        """get_file raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="GetFile"):
            await proxy.get_file("file_123", "token_abc")

    async def test_put_file_not_implemented(self, proxy):
        """put_file raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="PutFile"):
            await proxy.put_file("file_123", "token_abc", b"content")


class TestMainEntryPoint:
    """Tests for the main() CLI entry point."""

    def test_main_creates_proxy_and_calls_cli(self):
        """main() creates WopiProxy and invokes CLI."""
        from unittest.mock import MagicMock, patch

        mock_cli = MagicMock()

        with patch("genro_wopi.WopiProxy") as mock_proxy_cls:
            mock_proxy = MagicMock()
            mock_proxy.cli.return_value = mock_cli
            mock_proxy_cls.return_value = mock_proxy

            from genro_wopi import main

            main()

            mock_proxy_cls.assert_called_once()
            mock_proxy.cli.assert_called_once()
            mock_cli.assert_called_once()
