# WOPI Architecture - Internal Documentation

**Version**: 0.1.0
**Last Updated**: 2026-02-01
**Status**: 🔴 DA REVISIONARE

## Overview

This document describes the architectural model for integrating Collabora Online with Genropy applications via the WOPI (Web Application Open Platform Interface) protocol.

## Key Concepts

### What is WOPI?

WOPI is a REST-based protocol that enables office applications (like Collabora Online) to access and edit files stored in a host application. The protocol defines how the office application communicates with the file storage system.

```
┌─────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Browser   │      │    Collabora    │      │   WOPI Host     │
│   (User)    │      │    (Editor)     │      │   (genro-wopi)  │
└──────┬──────┘      └────────┬────────┘      └────────┬────────┘
       │                      │                        │
       │  1. Open document    │                        │
       │─────────────────────▶│                        │
       │                      │  2. CheckFileInfo      │
       │                      │───────────────────────▶│
       │                      │                        │
       │                      │  3. GetFile            │
       │                      │───────────────────────▶│
       │                      │                        │
       │  4. Edit in browser  │                        │
       │◀────────────────────▶│                        │
       │                      │                        │
       │                      │  5. PutFile (save)     │
       │                      │───────────────────────▶│
       │                      │                        │
```

### Components

| Component | Role | Example |
|-----------|------|---------|
| **Browser** | User interface, loads Collabora in iframe | User's browser |
| **Collabora** | Office editor (renders/edits documents) | `collabora.example.com` |
| **WOPI Host** | File storage and access management | `wopi.softwell.it` (genro-wopi) |
| **Gestionale** | Application generating document URLs | Genropy application |

## Deployment Model

### Central WOPI Host (Recommended)

genro-wopi runs as a centralized service managed by Softwell. Tenants can use either:
- A shared Collabora instance (Softwell pool)
- Their own Collabora instance (customer-managed)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SOFTWELL INFRASTRUCTURE                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     genro-wopi                               │   │
│  │                   wopi.softwell.it                           │   │
│  │                                                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │
│  │  │Tenant A │  │Tenant B │  │Tenant C │  │Tenant D │        │   │
│  │  │config   │  │config   │  │config   │  │config   │        │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │   │
│  │       │            │            │            │              │   │
│  └───────┼────────────┼────────────┼────────────┼──────────────┘   │
│          │            │            │            │                  │
│          ▼            │            │            ▼                  │
│  ┌───────────────┐    │            │    ┌───────────────┐         │
│  │ Collabora     │    │            │    │ (disabled)    │         │
│  │ Pool Softwell │    │            │    │               │         │
│  │ collabora.    │    │            │    │               │         │
│  │ softwell.it   │    │            │    │               │         │
│  └───────────────┘    │            │    └───────────────┘         │
│                       │            │                              │
└───────────────────────┼────────────┼──────────────────────────────┘
                        │            │
                        ▼            ▼
              ┌───────────────┐  ┌───────────────┐
              │ Collabora     │  │ Collabora     │
              │ Customer B    │  │ Customer C    │
              │ office.       │  │ collabora.    │
              │ customerb.com │  │ customerc.it  │
              └───────────────┘  └───────────────┘

              CUSTOMER INFRASTRUCTURE
```

### Tenant Configuration Options

| Option | Collabora Server | Managed By | Use Case |
|--------|------------------|------------|----------|
| **Pool** | `collabora.softwell.it` | Softwell | Small tenants, quick setup |
| **Own Server** | Customer's URL | Customer | Enterprise, compliance requirements |
| **Disabled** | None | - | Tenant doesn't need Office editing |

## Network Requirements

### WOPI Host Accessibility

The WOPI host (genro-wopi) must be accessible via HTTPS from any Collabora server that needs to use it.

```
Collabora (anywhere) ────HTTPS────▶ wopi.softwell.it (public)
```

### Collabora Whitelist

Each Collabora server must whitelist the WOPI host domain. This is a security feature that prevents unauthorized WOPI hosts from connecting.

```yaml
# Collabora configuration
WOPI_ALLOW_LIST: "wopi.softwell.it"
```

**Important**: When a customer uses their own Collabora server, they must add `wopi.softwell.it` to their whitelist.

## Collabora Licensing

### Understanding the License Model

Collabora Online is open source (MPLv2). There is **no license key** or runtime verification.

| Edition | Cost | What You Get |
|---------|------|--------------|
| **CODE** (Development) | Free | Full software, no support |
| **Business** | ~€1.82/user/month | Support, SLA, signed updates |
| **Enterprise** | Custom pricing | Priority support, customization |

### What "Licensing" Actually Means

- **Paying** = Access to support channels, SLA guarantees, signed security updates
- **Not paying** = Use CODE from Docker Hub, self-supported

The software itself is identical and doesn't check license status.

### Multi-Tenant Licensing Implications

Since licensing is a service contract (not a software key), each tenant can:

1. **Use Softwell Pool**: Licensing is Softwell's responsibility
2. **Use Own Collabora**: Licensing is customer's responsibility
3. **Disable Feature**: No licensing concerns

This "Bring Your Own License" model keeps Softwell out of per-user counting for customers who want their own infrastructure.

## WOPI Protocol Essentials

### Core Endpoints

genro-wopi must implement these WOPI endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/wopi/files/{file_id}` | GET | CheckFileInfo - file metadata |
| `/wopi/files/{file_id}/contents` | GET | GetFile - download file content |
| `/wopi/files/{file_id}/contents` | POST | PutFile - save file content |
| `/wopi/files/{file_id}` | POST | Lock/Unlock - concurrency control |

### Authentication Flow

```
1. Gestionale generates access_token (JWT) for document access
2. URL format: https://collabora.example.com/browser/xxx/cool.html?
               WOPISrc=https://wopi.softwell.it/wopi/files/FILE_ID&
               access_token=JWT_TOKEN
3. Collabora calls WOPI endpoints with access_token
4. genro-wopi validates token and serves/saves file
```

### Token Contents (Typical)

```json
{
  "file_id": "abc123",
  "tenant_id": "acme",
  "user_id": "user456",
  "permissions": ["view", "edit"],
  "exp": 1234567890
}
```

## Configuration Example

### Per-Tenant Configuration

```python
{
    "tenant_id": "acme",
    "wopi": {
        "enabled": True,
        "mode": "own",  # "pool" | "own" | "disabled"
        "collabora_url": "https://office.acme.it",  # only for mode="own"
    }
}
```

### Resolving Collabora URL

```python
DEFAULT_COLLABORA_URL = "https://collabora.softwell.it"

def get_collabora_url(tenant_id: str) -> str | None:
    config = get_tenant_config(tenant_id)

    if not config.wopi.enabled or config.wopi.mode == "disabled":
        return None

    if config.wopi.mode == "own":
        return config.wopi.collabora_url

    return DEFAULT_COLLABORA_URL  # pool mode
```

## Data Flow Summary

### Opening a Document

```
1. User clicks "Edit" in Gestionale

2. Gestionale (backend):
   - Determines tenant's Collabora URL
   - Generates JWT access_token
   - Returns editor URL to browser

3. Browser loads iframe:
   https://[collabora-url]/browser/[discovery]/cool.html?
   WOPISrc=https://wopi.softwell.it/wopi/files/[file_id]&
   access_token=[jwt]

4. Collabora server:
   - Loads editor UI
   - Calls CheckFileInfo on WOPI host
   - Calls GetFile to load document
   - Renders document in browser

5. User edits document

6. Collabora server:
   - Periodically calls PutFile to save
   - Manages locks for concurrent editing
```

## Security Considerations

### Token Security

- Access tokens should be short-lived (e.g., 1 hour)
- Tokens are tied to specific file_id and user
- WOPI host validates token on every request

### Network Security

- All communication over HTTPS
- Collabora whitelist prevents unauthorized WOPI hosts
- WOPI host can validate Collabora's Proof headers (optional)

### Tenant Isolation

- Each tenant's files are isolated by tenant_id in token
- Token cannot access files from other tenants
- Storage backend enforces tenant boundaries

## Appendix: Collabora Configuration

### Enabling WOPI Host

In Collabora's `coolwsd.xml` or via environment variables:

```xml
<storage>
    <wopi>
        <host allow="true">wopi\.softwell\.it</host>
    </wopi>
</storage>
```

Or via Docker:

```bash
docker run -e "domain=wopi\\.softwell\\.it" collabora/code
```

### Discovery Endpoint

Collabora exposes `/hosting/discovery` which returns available actions and URL patterns. genro-wopi may cache this to build correct editor URLs.

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-02-01 | Initial internal draft |
