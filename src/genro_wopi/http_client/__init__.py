# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""HTTP client for connecting to WOPI servers.

Example:
    >>> from tools.http_client import WopiProxyClient, connect
    >>> proxy = WopiProxyClient("http://localhost:8000", token="secret")
    >>> proxy.status()
    {'ok': True, 'active': True}
"""

from .client import WopiProxyClient, connect, register_connection

__all__ = [
    "WopiProxyClient",
    "connect",
    "register_connection",
]
