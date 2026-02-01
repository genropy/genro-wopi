
genro-wopi
==========

A WOPI proxy that enables document editing with Collabora Online, OnlyOffice, and other WOPI-compatible editors.

What it does
------------

genro-wopi sits between your application and WOPI-compatible document editors (Collabora Online,
OnlyOffice, Microsoft 365). Your application creates editing sessions via REST API; the proxy
handles the WOPI protocol communication.

- **Session management**: Create, track, and expire editing sessions
- **Multi-tenant**: Multiple organizations can share one instance with data isolation
- **Storage agnostic**: Works with any storage backend via genro-storage interface
- **Locking**: Collaborative editing with WOPI lock management
- **Audit trail**: All operations logged for compliance
- **Bring Your Own Editor**: Use Softwell's Collabora pool or your own WOPI client

Architecture
~~~~~~~~~~~~

.. code-block:: text

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

The proxy exposes a FastAPI REST API for session management and implements the WOPI protocol
endpoints that the document editor calls to access files.

When to use it
--------------

Consider this proxy when:

- **Document editing** is needed in your web application (spreadsheets, documents, presentations)
- **Multi-tenant isolation** is required for different organizations
- **Central control** over which editors can access which files
- **Audit logging** of document access and modifications is required

Quick start
-----------

**CLI**:

.. code-block:: bash

   pip install genro-wopi
   wopi-proxy serve --port 8000

**Docker**:

.. code-block:: bash

   docker run -p 8000:8000 genro-wopi

Then create a session and open the editor URL in an iframe.

Command-line interface
----------------------

The ``wopi-proxy`` CLI manages the service:

.. code-block:: bash

   # Start the server
   wopi-proxy serve --port 8000

   # Tenant management
   wopi-proxy tenants list
   wopi-proxy tenants add --id acme --name "ACME Corp"

   # Storage configuration
   wopi-proxy storages list
   wopi-proxy storages add --tenant-id acme --name attachments --protocol s3

   # Session management
   wopi-proxy sessions list
   wopi-proxy sessions cleanup --dry-run

API Endpoints
-------------

Session Management:

- ``POST /sessions/create`` - Create a new editing session
- ``GET /sessions/list`` - List active sessions
- ``GET /sessions/get`` - Get session details
- ``POST /sessions/close`` - Close a session early
- ``POST /sessions/cleanup`` - Remove expired sessions

WOPI Protocol (called by editor):

- ``GET /wopi/files/{file_id}`` - CheckFileInfo
- ``GET /wopi/files/{file_id}/contents`` - GetFile
- ``POST /wopi/files/{file_id}/contents`` - PutFile
- ``POST /wopi/files/{file_id}`` - Lock/Unlock operations

.. toctree::
   :maxdepth: 2
   :hidden:

   modules
