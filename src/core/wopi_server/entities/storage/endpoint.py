# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Storage endpoint: CRUD operations for tenant storage backends.

Designed for introspection by api_base/cli_base to auto-generate routes/commands.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...interface.endpoint_base import POST, BaseEndpoint

# Template directory for empty Office documents
# endpoint.py is in entities/storage/, templates are in wopi_server/templates/
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# Map extensions to template files
TEMPLATE_EXTENSIONS = {
    ".docx": "empty.docx",
    ".xlsx": "empty.xlsx",
    ".pptx": "empty.pptx",
    ".odt": "empty.odt",
    ".ods": "empty.ods",
    ".odp": "empty.odp",
}

if TYPE_CHECKING:
    from .table import StoragesTable


class StorageEndpoint(BaseEndpoint):
    """Storage management endpoint. Methods are introspected for API/CLI generation."""

    name = "storages"

    def __init__(self, table: StoragesTable):
        super().__init__(table)

    @POST
    async def add(
        self,
        tenant_id: str,
        name: str,
        protocol: str,
        config: dict[str, Any] | None = None,
    ) -> dict:
        """Add or update a storage backend for a tenant.

        Args:
            tenant_id: The tenant ID.
            name: Storage name (e.g., "HOME", "SALES").
            protocol: Storage protocol (local, s3, gcs, azure).
            config: Protocol-specific configuration.

        For local protocol:
            config: {"base_path": "/data/files"}

        For S3 protocol (EE only):
            config: {"bucket": "my-bucket", "prefix": "files/",
                    "aws_access_key_id": "...", "aws_secret_access_key": "..."}

        For GCS protocol (EE only):
            config: {"bucket": "my-bucket", "prefix": "files/",
                    "project": "...", "token": "..."}

        For Azure protocol (EE only):
            config: {"container": "my-container", "prefix": "files/",
                    "account_name": "...", "account_key": "..."}
        """
        data = {
            "tenant_id": tenant_id,
            "name": name,
            "protocol": protocol,
            "config": config or {},
        }
        await self.table.add(data)
        return await self.table.get(tenant_id, name)

    async def get(self, tenant_id: str, name: str) -> dict:
        """Get a single storage configuration."""
        return await self.table.get(tenant_id, name)

    async def list(self, tenant_id: str) -> list[dict]:
        """List all storage backends for a tenant."""
        return await self.table.list_all(tenant_id=tenant_id)

    @POST
    async def delete(self, tenant_id: str, name: str) -> dict:
        """Delete a storage backend."""
        deleted = await self.table.remove(tenant_id, name)
        return {"ok": deleted, "tenant_id": tenant_id, "name": name}

    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------

    async def list_files(self, storage_name: str, path: str = "/") -> list[dict]:
        """List files in a storage path.

        Args:
            storage_name: Storage backend name.
            path: Directory path within storage.

        Returns:
            List of file info dicts with name, type, size, mtime.
        """
        tenant_id = getattr(self, "_current_tenant_id", "default")
        manager = await self.table.get_storage_manager(tenant_id)

        node = manager.node(f"{storage_name}:{path}")

        if not await node.exists():
            return []

        children = await node.children()
        result = []
        for child in children:
            is_dir = await child.is_dir()
            info = {
                "name": child.basename,
                "type": "dir" if is_dir else "file",
                "path": child.path,
            }
            if not is_dir:
                try:
                    info["size"] = await child.size()
                    info["mtime"] = await child.mtime()
                except Exception:
                    info["size"] = 0
                    info["mtime"] = 0
            result.append(info)
        return result

    @POST
    async def create_file(
        self,
        storage_name: str,
        path: str | None = None,
        file_path: str | None = None,
        content: str = "",
        file_type: str | None = None,
    ) -> dict:
        """Create a new file in storage.

        Args:
            storage_name: Storage backend name.
            path: File path within storage.
            file_path: Alias for path (for demo compatibility).
            content: Optional initial content (text).
            file_type: File type hint (ignored, for demo compatibility).

        Returns:
            Dict with ok=True and file info.
        """
        # Accept either path or file_path
        actual_path = path or file_path
        if not actual_path:
            raise ValueError("path or file_path is required")

        tenant_id = getattr(self, "_current_tenant_id", "default")
        manager = await self.table.get_storage_manager(tenant_id)

        node = manager.node(f"{storage_name}:{actual_path}")

        # Create parent directory if needed
        parent = node.parent
        if not await parent.exists():
            await parent.mkdir(parents=True, exist_ok=True)

        # For Office documents, use template; for others, use content
        ext = Path(actual_path).suffix.lower()
        if ext in TEMPLATE_EXTENSIONS:
            template_path = TEMPLATES_DIR / TEMPLATE_EXTENSIONS[ext]
            template_content = template_path.read_bytes()
            await node.write_bytes(template_content)
        else:
            await node.write_text(content)

        return {
            "ok": True,
            "path": node.path,
            "name": node.basename,
            "storage_name": storage_name,
        }

    @POST
    async def upload_file(
        self,
        storage_name: str,
        path: str,
        file_content: str,
    ) -> dict:
        """Upload a file to storage.

        Args:
            storage_name: Storage backend name.
            path: Destination path within storage.
            file_content: File content (base64 encoded).

        Returns:
            Dict with ok=True and file info.
        """
        tenant_id = getattr(self, "_current_tenant_id", "default")
        manager = await self.table.get_storage_manager(tenant_id)
        node = manager.node(f"{storage_name}:{path}")

        # Create parent directory if needed
        parent = node.parent
        if not await parent.exists():
            await parent.mkdir(parents=True, exist_ok=True)

        # Decode base64 and write
        content = base64.b64decode(file_content)
        await node.write_bytes(content)

        return {
            "ok": True,
            "path": node.path,
            "name": node.basename,
            "size": len(content),
            "storage_name": storage_name,
        }

    @POST
    async def delete_file(self, storage_name: str, path: str) -> dict:
        """Delete a file or folder from storage.

        Args:
            storage_name: Storage backend name.
            path: File or folder path within storage.

        Returns:
            Dict with ok=True/False.
        """
        tenant_id = getattr(self, "_current_tenant_id", "default")
        manager = await self.table.get_storage_manager(tenant_id)

        node = manager.node(f"{storage_name}:{path}")
        deleted = await node.delete()

        return {"ok": deleted, "path": path, "storage_name": storage_name}

    @POST
    async def create_folder(self, storage_name: str, path: str) -> dict:
        """Create a new folder in storage.

        Args:
            storage_name: Storage backend name.
            path: Folder path within storage.

        Returns:
            Dict with ok=True and folder info.
        """
        tenant_id = getattr(self, "_current_tenant_id", "default")
        manager = await self.table.get_storage_manager(tenant_id)

        node = manager.node(f"{storage_name}:{path}")
        await node.mkdir(parents=True, exist_ok=True)

        return {
            "ok": True,
            "path": node.path,
            "name": node.basename,
            "storage_name": storage_name,
        }


__all__ = ["StorageEndpoint"]
