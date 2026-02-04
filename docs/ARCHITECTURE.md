# Architettura genro-wopi - Server WOPI per Collabora Online

**Status**: 🔴 DA REVISIONARE
**Data**: 2025-02-01

## Obiettivo

Implementare un server WOPI per integrare Collabora Online con i gestionali Genropy, permettendo di visualizzare/editare documenti Office (Word, Excel, etc.) direttamente in iframe nelle pagine SPA.

## Architettura

### Modello Multi-Tenant/Account

Riuso dell'architettura di genro-mail-proxy:

```text
Tenant (cliente/azienda)
  └── Account (licenza Collabora / ufficio)
        └── Files (documenti accessibili via WOPI)
```

- **Tenant**: Isolamento per cliente/azienda
- **Account**: Una licenza Collabora (può essere per ufficio/utente)
  - Configurazione URL Collabora
  - Credenziali/limiti
  - Storage associato

### Identificazione File (Configurabile per Account)

Due modalità, configurabili a livello account:

#### Modalità 1: Stateful (con tabella files)

Il WOPI server mantiene una tabella `files` che mappa:

```yaml
files:
  - pk: UUID (usato come file_id WOPI)
  - tenant_id: FK -> tenants
  - account_id: FK -> accounts
  - storage_ref: "storage_name:path/to/file.xlsx"
  - original_name: "documento.xlsx"
  - permissions: "view" | "edit"
  - user_id: chi ha aperto il file
  - lock_id: per WOPI locking
  - lock_expires_at: scadenza lock
  - created_at, updated_at
  - expires_at: (opzionale, per link temporanei)
```

**Vantaggi**: Audit trail, statistiche, gestione lock persistente, cleanup automatico.

**Flusso**:

1. Gestionale chiama `POST /files/register` per registrare un file
2. WOPI server restituisce `file_id` (UUID) e `access_token`
3. Gestionale costruisce URL iframe con questi parametri

#### Modalità 2: Stateless (JWT-based)

Il `file_id` è un JWT firmato contenente:

```json
{
  "storage_ref": "DOCUMENTS:fatture/2024/doc.xlsx",
  "user_id": "user123",
  "permissions": "edit",
  "exp": 1706800000
}
```

**Vantaggi**: Nessun stato server-side, scalabilità orizzontale, semplicità.

**Flusso**:

1. Gestionale genera direttamente il JWT (usando secret condiviso con account)
2. Gestionale costruisce URL iframe
3. Nessuna chiamata al WOPI server prima dell'apertura

#### Configurazione Account

```python
accounts:
  - file_mode: "stateful" | "stateless"  # default: stateful
  - jwt_secret: "..."  # per modalità stateless
```

**Nota**: In modalità stateless, il locking è comunque gestito in memoria (non persistente).

### Autenticazione

**Livello 1 - Gestionale → WOPI Server**:

- API key per account (come genro-mail-proxy)
- Header `X-API-Token`

**Livello 2 - WOPI access_token**:

- Token JWT firmato contenente: file_id, user_id, permissions, expiry
- Il gestionale lo genera, il WOPI server lo valida
- Secret condiviso per account o globale

### Endpoint WOPI Standard

```text
GET  /wopi/files/{file_id}                    # CheckFileInfo
GET  /wopi/files/{file_id}/contents           # GetFile
POST /wopi/files/{file_id}/contents           # PutFile
POST /wopi/files/{file_id}                    # Lock/Unlock/etc (X-WOPI-Override header)
```

### Endpoint Gestione (API REST)

```text
# Accounts
POST   /accounts/add
GET    /accounts/list
DELETE /accounts/remove

# Files
POST   /files/register      # Registra file per editing
GET    /files/list
DELETE /files/remove
GET    /files/get_edit_url  # Costruisce URL completo per iframe

# Storages (riuso da mail-proxy)
POST   /storages/add
GET    /storages/list
```

## Struttura Progetto

```text
genro-wopi/
├── src/
│   ├── genro_wopi/               # Package principale
│   │   └── __init__.py
│   ├── core/
│   │   └── wopi_server/
│   │       ├── __init__.py
│   │       ├── proxy_base.py     # WopiServerBase (riuso pattern)
│   │       ├── proxy.py          # WopiServer
│   │       ├── proxy_config.py   # Configurazione
│   │       ├── server.py         # Entry point uvicorn
│   │       ├── entities/
│   │       │   ├── tenant/       # Riuso quasi identico
│   │       │   ├── account/      # Adattato per Collabora
│   │       │   ├── file/         # NUOVO: registro file (stateful mode)
│   │       │   ├── storage/      # Riuso da mail-proxy
│   │       │   └── instance/
│   │       ├── interface/
│   │       │   ├── api_base.py
│   │       │   ├── endpoint_base.py
│   │       │   └── wopi_routes.py # Endpoint WOPI specifici
│   │       └── wopi/
│   │           ├── protocol.py   # Implementazione WOPI
│   │           ├── token.py      # JWT handling
│   │           └── lock.py       # Lock management
│   ├── sql/                      # Copia da mail-proxy
│   ├── storage/                  # Copia da mail-proxy
│   └── tools/                    # Encryption, etc.
├── tests/
├── pyproject.toml
└── README.md
```

## Componenti da Riusare (da genro-mail-proxy)

1. **sql/**: Intero modulo (SqlDb, Table, Column, adapters)
2. **storage/**: StorageManager, StorageNode
3. **tools/encryption.py**: Per credenziali
4. **core/.../interface/**: api_base.py, endpoint_base.py (adattati)
5. **core/.../entities/tenant/**: Quasi identico
6. **Architettura autodiscovery**: Pattern CE/EE

## Componenti Nuovi

1. **entities/account/**: Campi specifici Collabora (URL, API key Collabora)
2. **entities/file/**: Registro file per WOPI
3. **wopi/protocol.py**: Implementazione endpoint WOPI
4. **wopi/token.py**: Generazione/validazione JWT
5. **wopi/lock.py**: Gestione lock WOPI

## Dipendenze

```toml
[project]
dependencies = [
    "fastapi>=0.100",
    "uvicorn[standard]>=0.20",
    "aiosqlite>=0.19",
    "asyncpg>=0.28",           # PostgreSQL
    "pyjwt>=2.8",              # JWT tokens
    "cryptography>=41",        # Encryption
    "httpx>=0.25",             # HTTP client
    "genro-toolbox",           # UUID, utilities
]
```

## Flusso Tipico

```text
1. Admin configura account Collabora:
   POST /accounts/add {
     "tenant_id": "acme",
     "id": "office-main",
     "collabora_url": "https://collabora.acme.com",
     "storage_name": "DOCUMENTS"
   }

2. Utente vuole editare documento:
   - Gestionale chiama: POST /files/register {
       "tenant_id": "acme",
       "account_id": "office-main",
       "storage_ref": "DOCUMENTS:fatture/2024/doc.xlsx",
       "user_id": "user123",
       "permissions": "edit"
     }
   - Risposta: { "file_id": "uuid...", "edit_url": "https://collabora.../WOPISrc=..." }

3. Gestionale mostra iframe con edit_url

4. Collabora chiama WOPI server:
   - GET /wopi/files/{file_id}?access_token=... → CheckFileInfo
   - GET /wopi/files/{file_id}/contents?access_token=... → GetFile
   - POST /wopi/files/{file_id}/contents?access_token=... → PutFile (salvataggio)
```

## Decisioni Prese

1. **Locking**: Lock di base (Lock/Unlock standard WOPI, senza recovery avanzato)
2. **File Mode**: Configurabile per account (stateful con tabella / stateless con JWT)
3. **Location**: `sub-projects/genro-wopi` dentro meta-genro-modules

## Domande Aperte

1. **Versioning**: Tenere storico versioni dei file? (per ora: no, futuro EE)
2. **Cleanup**: Come gestire file registrati ma mai usati / token scaduti? (cron job periodico)
3. **Discovery**: Implementare WOPI discovery endpoint per auto-configurazione? (per ora: no)

## Verifica

1. Test unitari per ogni endpoint WOPI
2. Test integrazione con Collabora CODE (versione development)
3. Test multi-tenant isolation
4. Test storage locale e (EE) cloud

---

## Fonti

- [WOPI Protocol - Microsoft Docs](https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/)
- [Collabora Online SDK Examples](https://github.com/CollaboraOnline/collabora-online-sdk-examples/blob/master/webapp/php/wopi/endpoints.php)
- [cs3org/wopiserver](https://github.com/cs3org/wopiserver)
- [WOPI Wikipedia](https://en.m.wikipedia.org/wiki/Web_Application_Open_Platform_Interface)
