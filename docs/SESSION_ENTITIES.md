# Session Entities - Internal Documentation

**Version**: 0.1.0
**Last Updated**: 2026-02-01
**Status**: 🔴 DA REVISIONARE

## Overview

This document describes the database entities required for WOPI session management in genro-wopi.

## Entities Summary

| Entity | Table | Purpose |
|--------|-------|---------|
| **Session** | `sessions` | Active WOPI editing sessions |
| **Tenant** | `tenants` | Tenant configurations (already exists) |
| **Storage** | `storages` | Storage backends per tenant (already exists) |
| **CommandLog** | `command_log` | Audit trail (already exists) |

## Session Entity

### Purpose

Tracks active WOPI editing sessions. A session is created when Genropy requests document access and expires after `wopi_token_ttl` seconds.

### Table Schema: `sessions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Session identifier (UUID) |
| `tenant_id` | String (FK) | Tenant identifier |
| `storage_name` | String | Storage backend name |
| `file_path` | String | Path to document in storage |
| `file_id` | String | WOPI file_id (for URL) |
| `access_token` | String | WOPI access token (JWT) |
| `permissions` | String (JSON) | `["view"]` or `["view", "edit"]` |
| `account` | String | Account for audit (required) |
| `user` | String | User name (optional, for collaborative) |
| `origin_connection_id` | String | Genropy connection for callbacks |
| `origin_page_id` | String | Genropy page context |
| `lock_id` | String | Current lock ID (if locked) |
| `lock_expires_at` | Timestamp | Lock expiration |
| `created_at` | Timestamp | Session creation time |
| `expires_at` | Timestamp | Session expiration time |
| `last_accessed_at` | Timestamp | Last WOPI operation time |

### Session Lifecycle

```
1. CREATE: Genropy calls POST /api/sessions/create
   → Session created with access_token
   → Returns editor_url with WOPISrc and token

2. ACTIVE: WOPI client makes requests
   → CheckFileInfo: Validate token, return metadata
   → GetFile: Return file content
   → Lock/Unlock: Manage concurrent access
   → PutFile: Save changes (if edit permission)

3. EXPIRE: Token TTL exceeded
   → Session marked expired
   → Subsequent requests rejected

4. CLEANUP: Background task
   → Remove expired sessions
   → Release orphaned locks
```

### Session States

| State | Condition | Actions Allowed |
|-------|-----------|-----------------|
| **active** | `expires_at > now()` | All WOPI operations |
| **locked** | `lock_id IS NOT NULL` | Only lock holder can edit |
| **expired** | `expires_at <= now()` | None (cleanup pending) |

## SessionsTable API

### Core Methods

```python
class SessionsTable(Table):
    name = "sessions"
    pkey = "id"

    async def create_session(
        self,
        tenant_id: str,
        storage_name: str,
        file_path: str,
        permissions: list[str],
        account: str,
        user: str | None = None,
        origin_connection_id: str | None = None,
        origin_page_id: str | None = None,
        ttl_seconds: int = 3600,
    ) -> dict:
        """Create a new WOPI session."""

    async def get_by_token(self, access_token: str) -> dict | None:
        """Retrieve session by access token (for WOPI validation)."""

    async def get_by_file_id(self, file_id: str) -> dict | None:
        """Retrieve session by WOPI file_id."""

    async def update_last_accessed(self, session_id: str) -> None:
        """Update last_accessed_at timestamp."""

    async def set_lock(
        self, session_id: str, lock_id: str, ttl_seconds: int = 1800
    ) -> bool:
        """Set lock on session (returns False if already locked)."""

    async def release_lock(self, session_id: str, lock_id: str) -> bool:
        """Release lock (returns False if lock_id doesn't match)."""

    async def get_lock(self, session_id: str) -> str | None:
        """Get current lock_id or None."""

    async def cleanup_expired(self) -> int:
        """Remove expired sessions, return count deleted."""

    async def list_active(
        self, tenant_id: str | None = None
    ) -> list[dict]:
        """List active (non-expired) sessions."""
```

## SessionEndpoint API

### REST Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/sessions/create` | Create new session |
| GET | `/api/sessions/{session_id}` | Get session info |
| GET | `/api/sessions` | List active sessions |
| POST | `/api/sessions/{session_id}/close` | Close session early |
| POST | `/api/sessions/cleanup` | Remove expired sessions |

### Session Creation

**Request:**
```
POST /api/sessions/create
Authorization: Bearer <tenant_api_key>

{
  "storage_name": "attachments",
  "file_path": "ordini/12345/preventivo.xlsx",
  "permissions": ["view"],
  "account": "sales",
  "user": "Mario Rossi",
  "origin_connection_id": "conn_abc123",
  "origin_page_id": "ordini_detail_12345"
}
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "file_id": "file_xyz789",
  "editor_url": "https://collabora.softwell.it/browser/xxx/cool.html?WOPISrc=https://wopi.softwell.it/wopi/files/file_xyz789&access_token=eyJ...",
  "expires_at": "2026-02-01T12:00:00Z"
}
```

### CLI Commands

```bash
# List active sessions
wopi-server sessions list [--tenant-id TENANT]

# Get session details
wopi-server sessions get --session-id SESSION_ID

# Close session
wopi-server sessions close --session-id SESSION_ID

# Cleanup expired sessions
wopi-server sessions cleanup [--dry-run]
```

## WOPI Protocol Endpoints

These endpoints are called by the WOPI client (Collabora/OnlyOffice), not by Genropy.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/wopi/files/{file_id}` | CheckFileInfo |
| GET | `/wopi/files/{file_id}/contents` | GetFile |
| POST | `/wopi/files/{file_id}/contents` | PutFile |
| POST | `/wopi/files/{file_id}` | Lock/Unlock/RefreshLock |

### CheckFileInfo Response

```json
{
  "BaseFileName": "preventivo.xlsx",
  "Size": 12345,
  "OwnerId": "acme",
  "UserId": "Mario Rossi",
  "UserFriendlyName": "Mario Rossi",
  "Version": "v1",
  "UserCanWrite": true,
  "UserCanNotWriteRelative": true,
  "SupportsLocks": true,
  "SupportsUpdate": true
}
```

## Callback Events

When `origin_connection_id` is provided, genro-wopi sends callbacks:

| Event | When | Payload |
|-------|------|---------|
| `session_created` | Session created | session_id, file_path |
| `document_opened` | First GetFile | session_id |
| `document_saved` | PutFile success | session_id, file_path, version |
| `lock_acquired` | Lock obtained | session_id, lock_id |
| `lock_released` | Lock released | session_id |
| `session_expired` | Session timeout | session_id |

## Audit Integration

All session operations are logged to `command_log`:

```python
await command_log.log_command(
    tenant_id="acme",
    account="sales",
    user="Mario Rossi",
    command="wopi.get_file",
    details={
        "session_id": "sess_abc123",
        "file_path": "ordini/12345/preventivo.xlsx",
    }
)
```

---

## Storage Integration

genro-wopi uses the **genro-storage** interface for all file operations. The storage layer is identical to genro-storage, ensuring consistency across the Genropy ecosystem.

### StorageManager Configuration

Storage backends are configured per tenant in the `storages` table:

```python
# Example storage configuration
{
    "name": "attachments",
    "tenant_id": "acme",
    "protocol": "s3",
    "bucket": "acme-documents",
    "prefix": "attachments/",
    "credentials": {...}
}
```

### StorageNode Interface

genro-wopi uses `StorageNode` for all file operations:

```python
# Get storage node for a file
storage = await wopi.get_storage(tenant_id, storage_name)
node = storage.node(file_path)

# Read operations
content = await node.read_bytes()
size = await node.size()
mtime = await node.mtime()
exists = await node.exists()

# Write operations (for PutFile)
await node.write_bytes(content)

# Metadata
info = {
    "basename": node.basename,      # "preventivo.xlsx"
    "size": await node.size(),      # 12345
    "mtime": await node.mtime(),    # Unix timestamp
    "mimetype": node.mimetype,      # "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}
```

### Versioning Support

If the storage backend supports versioning (e.g., S3 with versioning enabled), genro-wopi can:

1. **Return version info in CheckFileInfo**:
```python
# Check if versioning is supported
if node.capabilities.versioning:
    version = node.versions[0]["version_id"] if node.versions else "v1"
else:
    version = f"v{int(await node.mtime())}"
```

2. **Access specific versions**:
```python
# Access a specific version (read-only)
node_v2 = storage.node(file_path, version="abc123")
content = await node_v2.read_bytes()

# List available versions
if node.capabilities.version_listing:
    versions = node.versions  # list[dict] with version_id, mtime, size
    count = node.version_count
```

3. **Write creates new version** (automatic with versioned backends):
```python
# Write always creates a new version on versioned storage
await node.write_bytes(new_content)
# Previous version is preserved automatically
```

### Backend Capabilities

The storage backend declares its capabilities:

```python
@dataclass(frozen=True)
class BackendCapabilities:
    # Core operations
    read: bool = True
    write: bool = True
    delete: bool = True

    # Versioning support
    versioning: bool = False          # Backend supports versions
    version_listing: bool = False     # Can list versions
    version_access: bool = False      # Can read specific versions

    # Other capabilities
    presigned_urls: bool = False      # Can generate presigned URLs
    hash_on_metadata: bool = False    # MD5 available without reading
```

### WOPI Version Handling

WOPI protocol uses version strings for conflict detection:

| Operation | Version Handling |
|-----------|------------------|
| **CheckFileInfo** | Return current version in `Version` field |
| **GetFile** | Optional `X-WOPI-ItemVersion` header |
| **PutFile** | Check `X-WOPI-Lock` for conflicts |

```python
async def check_file_info(self, session: dict) -> dict:
    node = await self.get_node(session)

    # Get version string
    if node.capabilities.versioning and node.versions:
        version = node.versions[0]["version_id"]
    else:
        version = f"v{int(await node.mtime())}"

    return {
        "BaseFileName": node.basename,
        "Size": await node.size(),
        "Version": version,
        # ...
    }
```

### Supported Backends

genro-wopi inherits all backends from genro-storage:

| Backend | Versioning | Use Case |
|---------|------------|----------|
| **local** | No | Development, on-premise |
| **s3** | Yes* | Production (AWS, MinIO) |
| **gcs** | Yes* | Google Cloud |
| **azure** | Yes* | Azure Blob |
| **webdav** | No | Nextcloud, ownCloud |

*Versioning depends on bucket/container configuration.

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-02-01 | Initial draft |
