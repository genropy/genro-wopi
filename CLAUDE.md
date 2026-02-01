# Claude Code Instructions - genro-wopi

**Parent Document**: This project follows all policies from the central [meta-genro-modules CLAUDE.md](https://github.com/softwellsrl/meta-genro-modules/blob/main/CLAUDE.md)

## Project-Specific Context

### Current Status
- Development Status: Alpha
- Has Implementation: Yes (core infrastructure)

### Project Description
WOPI (Web Application Open Platform Interface) implementation for the Genropy framework -
enables integration with Collabora Online, LibreOffice Online, and other WOPI-compatible editors.

### Architecture

The codebase is structured as follows:

```
src/
├── sql/              # Database abstraction (SqlDb, Table, adapters)
├── storage/          # File storage abstraction (StorageManager, StorageNode)
├── tools/            # Utilities (encryption, repl, http_client)
└── core/
    └── wopi_server/
        ├── interface/    # API/CLI auto-generation via introspection
        ├── entities/     # Database entities (instance, tenant, storage, command_log)
        ├── wopi_config.py   # Configuration dataclass
        ├── wopi_base.py     # Foundation class
        └── wopi_proxy.py    # Main WOPI proxy (protocol handlers TBD)
```

### Multi-Tenant WOPI Model

Tenants can operate in three modes:
- **pool**: Use Softwell shared Collabora server (default)
- **own**: Use tenant's own Collabora server (requires collabora_url)
- **disabled**: WOPI editing disabled

### Key Files

- `src/core/wopi_server/wopi_proxy.py` - Main entry point
- `src/core/wopi_server/wopi_config.py` - Configuration
- `docs/WOPI_ARCHITECTURE.md` - Internal architecture documentation

---

**All general policies are inherited from the parent document.**
