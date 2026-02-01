# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Optional tools and utilities for WOPI server."""

from genro_toolbox import get_uuid

from .encryption import decrypt_value, encrypt_value
from .repl import RESERVED_ATTR, REPLWrapper, is_reserved, repl_wrap, reserved

__all__ = [
    "RESERVED_ATTR",
    "REPLWrapper",
    "decrypt_value",
    "encrypt_value",
    "get_uuid",
    "is_reserved",
    "repl_wrap",
    "reserved",
]
