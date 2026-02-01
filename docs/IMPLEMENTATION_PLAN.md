# Implementation Plan - genro-wopi

**Version**: 0.1.0
**Last Updated**: 2026-02-01
**Status**: 🔴 DA REVISIONARE

## Overview

This document outlines the implementation plan for completing genro-wopi, from the current Alpha state (infrastructure copied from genro-mail-proxy) to a functional WOPI server.

## Current State

### Already Implemented (from genro-mail-proxy)

| Component | Status | Notes |
|-----------|--------|-------|
| `sql/` | ✅ Complete | Database abstraction layer |
| `storage/` | ✅ Complete | File storage abstraction |
| `tools/encryption` | ✅ Complete | AES-256-GCM cipher |
| `tools/repl` | ✅ Complete | REPL wrapper |
| `interface/` | ✅ Complete | API/CLI auto-generation |
| `entities/instance/` | ✅ Complete | Instance configuration |
| `entities/tenant/` | ✅ Complete | Tenant management (adapted for WOPI) |
| `entities/storage/` | ✅ Complete | Storage backends |
| `entities/command_log/` | ✅ Complete | Audit trail |
| `wopi_base.py` | ✅ Complete | Foundation class |
| `wopi_config.py` | ✅ Complete | Configuration dataclass |
| `wopi_proxy.py` | ⚠️ Stub | Only stub methods |

### To Implement

| Component | Priority | Description |
|-----------|----------|-------------|
| `entities/session/` | 🔴 High | Session management |
| WOPI protocol handlers | 🔴 High | CheckFileInfo, GetFile, PutFile, Lock |
| Session creation API | 🔴 High | `/api/sessions/create` |
| Storage integration | 🔴 High | genro-storage interface with versioning |
| Callback system | 🟡 Medium | Notify Genropy on events |
| Discovery caching | 🟢 Low | Cache WOPI client discovery |

---

## Phase 1: Session Entity

**Goal**: Implement the Session entity with table, endpoint, and full test coverage.

### 1.1 SessionsTable

**File**: `src/core/wopi_server/entities/session/table.py`

```python
class SessionsTable(Table):
    name = "sessions"
    pkey = "id"

    def configure(self) -> None:
        c = self.columns
        c.column("id", String)  # UUID
        c.column("tenant_id", String)
        c.column("storage_name", String)
        c.column("file_path", String)
        c.column("file_id", String)  # WOPI file_id
        c.column("access_token", String)
        c.column("permissions", String, json_encoded=True)
        c.column("account", String)
        c.column("user", String)
        c.column("origin_connection_id", String)
        c.column("origin_page_id", String)
        c.column("lock_id", String)
        c.column("lock_expires_at", Timestamp)
        c.column("created_at", Timestamp, default="CURRENT_TIMESTAMP")
        c.column("expires_at", Timestamp)
        c.column("last_accessed_at", Timestamp)
```

**Methods to implement**:
- `create_session()` - Create new session with JWT token
- `get_by_token()` - Lookup by access_token
- `get_by_file_id()` - Lookup by WOPI file_id
- `update_last_accessed()` - Touch timestamp
- `set_lock()` / `release_lock()` / `get_lock()` - Lock management
- `cleanup_expired()` - Remove old sessions
- `list_active()` - List non-expired sessions

### 1.2 SessionEndpoint

**File**: `src/core/wopi_server/entities/session/endpoint.py`

```python
class SessionEndpoint(BaseEndpoint):
    name = "sessions"

    @POST
    async def create(
        self,
        storage_name: str,
        file_path: str,
        permissions: list[str],
        account: str,
        user: str | None = None,
        origin_connection_id: str | None = None,
        origin_page_id: str | None = None,
    ) -> dict:
        """Create WOPI session, return editor_url."""

    async def get(self, session_id: str) -> dict:
        """Get session details."""

    async def list(self, tenant_id: str | None = None) -> list[dict]:
        """List active sessions."""

    @POST
    async def close(self, session_id: str) -> bool:
        """Close session early."""

    @POST
    async def cleanup(self, dry_run: bool = False) -> dict:
        """Remove expired sessions."""
```

### 1.3 Tests

**File**: `tests/test_session_table.py`

```python
# Test cases:
# - test_create_session_basic
# - test_create_session_with_user
# - test_create_session_with_callback_context
# - test_get_by_token_valid
# - test_get_by_token_invalid
# - test_get_by_token_expired
# - test_get_by_file_id
# - test_update_last_accessed
# - test_set_lock_success
# - test_set_lock_already_locked
# - test_release_lock_success
# - test_release_lock_wrong_id
# - test_cleanup_expired
# - test_list_active
# - test_list_active_by_tenant
```

**File**: `tests/test_session_endpoint.py`

```python
# Test cases:
# - test_create_session_api
# - test_create_session_missing_account (error)
# - test_create_session_invalid_storage (error)
# - test_get_session_api
# - test_get_session_not_found (error)
# - test_list_sessions_api
# - test_close_session_api
# - test_cleanup_sessions_api
# - test_cleanup_sessions_dry_run
```

**File**: `tests/test_session_cli.py`

```python
# Test cases:
# - test_sessions_list_cli
# - test_sessions_get_cli
# - test_sessions_close_cli
# - test_sessions_cleanup_cli
```

---

## Phase 1b: Storage Integration (genro-storage interface)

**Goal**: Integrate genro-storage for file operations with versioning support.

### 1b.1 Storage Access

genro-wopi uses the identical interface from genro-storage:

```python
# In WopiProxy
async def get_storage_node(self, session: dict) -> StorageNode:
    """Get StorageNode for session's file."""
    storage = await self.get_storage(session["tenant_id"], session["storage_name"])
    return storage.node(session["file_path"])
```

### 1b.2 StorageNode Interface (from genro-storage)

All file operations use `StorageNode`:

```python
# Read operations
content = await node.read_bytes()
size = await node.size()
mtime = await node.mtime()
exists = await node.exists()
mimetype = node.mimetype

# Write operations
await node.write_bytes(content)

# Versioning (if supported)
if node.capabilities.versioning:
    versions = node.versions          # list[dict]
    count = node.version_count
    version_id = versions[0]["version_id"]

# Access specific version (read-only)
node_v2 = storage.node(file_path, version="abc123")
old_content = await node_v2.read_bytes()
```

### 1b.3 Version Handling in WOPI

```python
async def get_file_version(self, node: StorageNode) -> str:
    """Get version string for WOPI protocol."""
    if node.capabilities.versioning and node.versions:
        return node.versions[0]["version_id"]
    else:
        # Fallback: use mtime as version
        return f"v{int(await node.mtime())}"
```

### 1b.4 Backend Capabilities Check

```python
async def check_file_info(self, session: dict) -> dict:
    node = await self.get_storage_node(session)

    # Version handling based on capabilities
    version = await self.get_file_version(node)

    # Capability-aware response
    return {
        "BaseFileName": node.basename,
        "Size": await node.size(),
        "Version": version,
        "UserCanWrite": "edit" in session["permissions"],
        "SupportsLocks": True,
        "SupportsUpdate": True,
        # Optional: expose version history if supported
        "SupportsGetFileWopiSrc": node.capabilities.version_access,
    }
```

### 1b.5 Tests

**File**: `tests/test_storage_integration.py`

```python
# Storage access tests:
# - test_get_storage_node
# - test_read_file_content
# - test_write_file_content
# - test_file_metadata (size, mtime, mimetype)

# Versioning tests (with mock versioned backend):
# - test_get_file_version_with_versioning
# - test_get_file_version_fallback_mtime
# - test_access_specific_version
# - test_write_creates_new_version
# - test_list_versions

# Backend capabilities tests:
# - test_check_capabilities_s3
# - test_check_capabilities_local
# - test_check_capabilities_webdav
```

---

## Phase 2: WOPI Protocol Handlers

**Goal**: Implement WOPI protocol endpoints called by Collabora/OnlyOffice.

### 2.1 CheckFileInfo

**Endpoint**: `GET /wopi/files/{file_id}`

```python
async def check_file_info(self, file_id: str, access_token: str) -> dict:
    """Return file metadata per WOPI spec."""
    session = await self.sessions.get_by_file_id(file_id)
    if not session or session["access_token"] != access_token:
        raise HTTPException(401, "Invalid token")

    if session["expires_at"] < datetime.utcnow():
        raise HTTPException(401, "Token expired")

    # Use genro-storage StorageNode interface
    node = await self.get_storage_node(session)

    # Get version (capabilities-aware)
    version = await self.get_file_version(node)

    return {
        "BaseFileName": node.basename,
        "Size": await node.size(),
        "OwnerId": session["tenant_id"],
        "UserId": session["user"] or session["account"],
        "UserFriendlyName": session["user"] or session["account"],
        "Version": version,
        "UserCanWrite": "edit" in session["permissions"],
        "SupportsLocks": True,
        "SupportsUpdate": True,
    }
```

### 2.2 GetFile

**Endpoint**: `GET /wopi/files/{file_id}/contents`

```python
async def get_file(self, file_id: str, access_token: str) -> StreamingResponse:
    """Return file content."""
    session = await self.validate_session(file_id, access_token)

    # Use genro-storage StorageNode
    node = await self.get_storage_node(session)

    await self.sessions.update_last_accessed(session["id"])
    await self.audit_log("wopi.get_file", session)

    content = await node.read_bytes()

    # Include version header if supported
    headers = {}
    if node.capabilities.versioning and node.versions:
        headers["X-WOPI-ItemVersion"] = node.versions[0]["version_id"]

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers=headers,
    )
```

### 2.3 PutFile

**Endpoint**: `POST /wopi/files/{file_id}/contents`

```python
async def put_file(
    self, file_id: str, access_token: str, content: bytes, lock_id: str | None
) -> dict:
    """Save file content."""
    session = await self.validate_session(file_id, access_token, require_edit=True)

    # Check lock
    current_lock = await self.sessions.get_lock(session["id"])
    if current_lock and current_lock != lock_id:
        raise HTTPException(409, "Lock mismatch")

    # Use genro-storage StorageNode
    node = await self.get_storage_node(session)

    # Write creates new version automatically on versioned backends
    await node.write_bytes(content)

    # Get new version for response
    new_version = await self.get_file_version(node)

    await self.sessions.update_last_accessed(session["id"])
    await self.audit_log("wopi.put_file", session)
    await self.send_callback(session, "document_saved", {"version": new_version})

    return {
        "status": "success",
        "version": new_version,
    }
```

### 2.4 Lock Operations

**Endpoint**: `POST /wopi/files/{file_id}` with X-WOPI-Override header

```python
async def handle_lock_operation(
    self, file_id: str, access_token: str, operation: str, lock_id: str
) -> dict:
    """Handle Lock, Unlock, RefreshLock, GetLock."""
    session = await self.validate_session(file_id, access_token)

    if operation == "LOCK":
        success = await self.sessions.set_lock(session["id"], lock_id)
        if not success:
            current = await self.sessions.get_lock(session["id"])
            raise HTTPException(409, headers={"X-WOPI-Lock": current})
        await self.send_callback(session, "lock_acquired")

    elif operation == "UNLOCK":
        success = await self.sessions.release_lock(session["id"], lock_id)
        if not success:
            raise HTTPException(409, "Lock mismatch")
        await self.send_callback(session, "lock_released")

    elif operation == "REFRESH_LOCK":
        # Extend lock TTL
        await self.sessions.set_lock(session["id"], lock_id)

    elif operation == "GET_LOCK":
        lock = await self.sessions.get_lock(session["id"])
        return Response(headers={"X-WOPI-Lock": lock or ""})

    return {"status": "success"}
```

### 2.5 Tests

**File**: `tests/test_wopi_protocol.py`

```python
# CheckFileInfo tests:
# - test_check_file_info_success
# - test_check_file_info_invalid_token
# - test_check_file_info_expired_token
# - test_check_file_info_view_only
# - test_check_file_info_edit_permission

# GetFile tests:
# - test_get_file_success
# - test_get_file_updates_last_accessed
# - test_get_file_creates_audit_log

# PutFile tests:
# - test_put_file_success
# - test_put_file_view_only_rejected
# - test_put_file_lock_mismatch
# - test_put_file_sends_callback

# Lock tests:
# - test_lock_success
# - test_lock_already_locked
# - test_unlock_success
# - test_unlock_wrong_id
# - test_refresh_lock
# - test_get_lock
```

---

## Phase 3: Callback System

**Goal**: Send HTTP callbacks to Genropy when document events occur.

### 3.1 Callback Client

**File**: `src/tools/http_client/callback.py`

```python
class CallbackClient:
    """Send callbacks to Genropy."""

    async def send_callback(
        self,
        tenant: dict,
        session: dict,
        event: str,
        extra_data: dict | None = None,
    ) -> bool:
        """Send callback to client_base_url."""
        if not tenant.get("client_base_url"):
            return False

        if not session.get("origin_connection_id"):
            return False

        payload = {
            "origin_connection_id": session["origin_connection_id"],
            "origin_page_id": session.get("origin_page_id"),
            "event": event,
            "session_id": session["id"],
            "file_path": session["file_path"],
            "timestamp": datetime.utcnow().isoformat(),
            **(extra_data or {}),
        }

        url = f"{tenant['client_base_url']}/wopi/callback"
        auth = tenant.get("client_auth")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=self._build_auth(auth),
                timeout=10.0,
            )
            return response.is_success
```

### 3.2 Tests

**File**: `tests/test_callback.py`

```python
# - test_send_callback_success
# - test_send_callback_no_base_url (skip)
# - test_send_callback_no_connection_id (skip)
# - test_send_callback_with_auth
# - test_send_callback_timeout_handling
# - test_send_callback_error_handling
```

---

## Phase 4: Integration & REPL

**Goal**: Complete integration testing and REPL support.

### 4.1 Integration Tests

**File**: `tests/test_integration.py`

```python
# Full flow tests:
# - test_full_view_flow
#   1. Create session
#   2. CheckFileInfo
#   3. GetFile
#   4. Session expires

# - test_full_edit_flow
#   1. Create session with edit
#   2. CheckFileInfo
#   3. GetFile
#   4. Lock
#   5. PutFile
#   6. Unlock
#   7. Verify callback sent

# - test_concurrent_edit_lock
#   1. User A creates session, locks
#   2. User B creates session, tries to lock (fails)
#   3. User A unlocks
#   4. User B locks (success)
```

### 4.2 REPL Support

The REPL is auto-generated from endpoints. Verify commands work:

```python
# REPL test cases:
# - test_repl_sessions_create
# - test_repl_sessions_list
# - test_repl_sessions_get
# - test_repl_sessions_close
# - test_repl_sessions_cleanup
```

### 4.3 CLI Tests

**File**: `tests/test_cli.py`

```python
# CLI integration tests:
# - test_cli_tenants_add
# - test_cli_tenants_list
# - test_cli_sessions_list
# - test_cli_sessions_cleanup
# - test_cli_instance_status
```

---

## Implementation Order

### Sprint 1: Session Entity (Foundation)

1. ☐ Create `entities/session/__init__.py`
2. ☐ Create `entities/session/table.py` with SessionsTable
3. ☐ Create `entities/session/endpoint.py` with SessionEndpoint
4. ☐ Register session entity in `wopi_base.py`
5. ☐ Write `tests/test_session_table.py`
6. ☐ Write `tests/test_session_endpoint.py`
7. ☐ Run tests, fix issues

### Sprint 1b: Storage Integration

1. ☐ Implement `get_storage_node()` in WopiProxy
2. ☐ Implement `get_file_version()` with capabilities check
3. ☐ Write `tests/test_storage_integration.py`
4. ☐ Test with mock versioned backend
5. ☐ Test with local backend (no versioning)

### Sprint 2: WOPI Protocol (Core)

1. ☐ Add WOPI routes to `wopi_proxy.py`
2. ☐ Implement `check_file_info()` with StorageNode
3. ☐ Implement `get_file()` with version header
4. ☐ Implement `put_file()` with version tracking
5. ☐ Implement lock operations
6. ☐ Write `tests/test_wopi_protocol.py`
7. ☐ Run tests, fix issues

### Sprint 3: Callbacks & Integration

1. ☐ Create `tools/http_client/callback.py`
2. ☐ Integrate callbacks in WOPI handlers
3. ☐ Write `tests/test_callback.py`
4. ☐ Write `tests/test_integration.py`
5. ☐ Run full test suite

### Sprint 4: CLI & REPL Polish

1. ☐ Write `tests/test_cli.py`
2. ☐ Write `tests/test_repl.py`
3. ☐ Documentation updates
4. ☐ Final cleanup and review

---

## Test Coverage Target

| Component | Target |
|-----------|--------|
| `entities/session/table.py` | 95% |
| `entities/session/endpoint.py` | 90% |
| `wopi_proxy.py` (WOPI handlers) | 90% |
| Storage integration (versioning) | 90% |
| `tools/http_client/callback.py` | 85% |
| Overall | 85% |

---

## Dependencies

### Required (already in pyproject.toml)

- `aiosqlite` - SQLite async
- `fastapi` - REST API
- `pydantic` - Validation
- `httpx` - HTTP client
- `cryptography` - JWT signing
- `genro-storage` - Storage abstraction with versioning (via genro-toolbox)

### Test Dependencies

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage
- `httpx` - Test client

### Storage Backend Dependencies (optional)

- `boto3` - S3 backend (versioning supported)
- `google-cloud-storage` - GCS backend (versioning supported)
- `azure-storage-blob` - Azure backend (versioning supported)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| WOPI spec compliance | Test against real Collabora instance |
| Lock race conditions | Use database transactions |
| Token security | Use short TTL, signed JWTs |
| Callback failures | Log and retry with backoff |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-02-01 | Initial draft |
