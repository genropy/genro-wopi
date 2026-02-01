# genro-wopi

[![PyPI version](https://img.shields.io/pypi/v/genro-wopi?style=flat)](https://pypi.org/project/genro-wopi/)
[![Tests](https://github.com/genropy/genro-wopi/actions/workflows/tests.yml/badge.svg)](https://github.com/genropy/genro-wopi/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/genropy/genro-wopi/branch/main/graph/badge.svg)](https://codecov.io/gh/genropy/genro-wopi)
[![Documentation](https://readthedocs.org/projects/genro-wopi/badge/?version=latest)](https://genro-wopi.readthedocs.io/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A WOPI proxy that enables document editing with Collabora Online, OnlyOffice, and other WOPI-compatible editors.

## What it does

genro-wopi sits between your application and WOPI-compatible document editors. Your application creates editing sessions via REST API; the proxy handles the WOPI protocol communication.

```text
┌─────────────┐      REST       ┌─────────────┐      WOPI       ┌─────────────┐
│ Application │ ──────────────► │ genro-wopi  │ ◄─────────────► │  Collabora  │
│  (Genropy)  │                 │   proxy     │                 │   Online    │
└─────────────┘                 └─────────────┘                 └─────────────┘
                                       │
                                       ▼
                                ┌─────────────┐
                                │   Storage   │
                                │ (S3, local) │
                                └─────────────┘
```

## Features

- **Session management**: Create, track, and expire editing sessions
- **Multi-tenant**: Multiple organizations can share one instance with data isolation
- **Storage agnostic**: Works with any storage backend via genro-storage interface
- **Locking**: Collaborative editing with WOPI lock management
- **Audit trail**: All operations logged for compliance
- **Bring Your Own Editor**: Use Softwell's Collabora pool or your own WOPI client

## Quick start

**CLI**:

```bash
pip install genro-wopi
wopi-proxy serve --port 8000
```

**Docker**:

```bash
docker run -p 8000:8000 genro-wopi
```

## Command-line interface

```bash
# Start the server
wopi-proxy serve --port 8000

# Tenant management
wopi-proxy tenants list
wopi-proxy tenants add --id acme --name "ACME Corp"

# Session management
wopi-proxy sessions list
wopi-proxy sessions cleanup --dry-run
```

## API Endpoints

**Session Management:**

- `POST /sessions/create` - Create a new editing session
- `GET /sessions/list` - List active sessions
- `POST /sessions/close` - Close a session early

**WOPI Protocol** (called by the editor):

- `GET /wopi/files/{file_id}` - CheckFileInfo
- `GET /wopi/files/{file_id}/contents` - GetFile
- `POST /wopi/files/{file_id}/contents` - PutFile

## Status

**Development Status: Beta**

Core infrastructure implemented. WOPI protocol handlers in development.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

Copyright 2025 Softwell S.r.l.
