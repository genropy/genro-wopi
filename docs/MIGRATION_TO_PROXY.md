# Guida alla Migrazione verso genro-proxy

**Versione**: 1.0
**Data**: 2025-02-03
**Stato**: 🔴 DA REVISIONARE - In corso di completamento

Questo documento descrive i passi necessari per adattare un progetto genro-* ad usare genro-proxy come base.

## Panoramica

genro-proxy fornisce l'infrastruttura comune per i microservizi Genro:
- `sql/` - Database abstraction layer (SqlDb, Table, Column)
- `storage/` - File storage abstraction (StorageManager, StorageNode)
- `interface/` - API/CLI auto-generation
- `encryption/` - EncryptionManager per campi cifrati
- `proxy_base.py` - Classe base ProxyBase da cui ereditare

## Fase 1: Aggiungere Dipendenza

### pyproject.toml

```toml
dependencies = [
    "genro-proxy @ git+https://github.com/genropy/genro-proxy.git@main",
    # ... altre dipendenze
]
```

**Nota**: Quando genro-proxy sarà pubblicato su PyPI, usare `genro-proxy>=0.1.0`.

## Fase 2: Rimuovere Codice Duplicato

### Cartelle da eliminare

Se il progetto ha copie locali di questi moduli, rimuoverle:

```bash
rm -rf src/sql/
rm -rf src/storage/
rm -rf src/core/<project>/interface/  # se presente
```

### File da eliminare

```bash
rm src/tools/encryption.py  # se presente
rm src/tools/repl.py        # se presente
```

## Fase 3: Aggiornare la Configurazione

### Prima (configurazione locale)

```python
from dataclasses import dataclass

@dataclass
class MyConfig:
    db_path: str = "data/my.db"
    port: int = 8000
    # ... altri campi
```

### Dopo (estendere ProxyConfigBase)

```python
from dataclasses import dataclass
from proxy.proxy_base import ProxyConfigBase

@dataclass
class MyConfig(ProxyConfigBase):
    """Configurazione specifica del progetto, estende ProxyConfigBase."""
    # Campi ereditati: db_path, instance_name, port, api_token, test_mode, start_active

    # Aggiungere solo campi specifici del progetto
    my_custom_field: str = "default_value"
```

## Fase 4: Aggiornare la Classe Base del Server

### Prima (implementazione locale)

```python
class MyServerBase:
    def __init__(self, config):
        self.config = config
        self.db = SqlDb(config.db_path)
        # ... setup manuale

    async def init(self):
        await self.db.connect()
        # ... inizializzazione manuale
```

### Dopo (ereditare da ProxyBase)

```python
from proxy.proxy_base import ProxyBase
from .my_config import MyConfig

class MyServerBase(ProxyBase):
    """Server base che eredita tutto da ProxyBase."""

    # Specificare i package dove cercare le entities
    entity_packages: list[str] = ["core.my_server.entities"]
    ee_entity_packages: list[str] = ["enterprise.my_server.entities"]  # opzionale
    encryption_key_env: str = "MY_ENCRYPTION_KEY"

    def __init__(self, config: MyConfig | None = None):
        super().__init__(config or MyConfig())

    async def init(self) -> None:
        await super().init()
        # Inizializzazione specifica del progetto (opzionale)
        async with self.db.connection():
            await self._my_custom_init()
```

**Attributi ereditati da ProxyBase**:
- `config`: Configurazione
- `db`: SqlDb con autodiscovery delle tabelle
- `encryption`: EncryptionManager
- `endpoints`: EndpointManager
- `api`: ApiManager (crea FastAPI app)
- `cli`: CliManager (crea Click group)

## Fase 5: Aggiornare gli Import

### Tabella di Sostituzione Import

| Prima | Dopo |
|-------|------|
| `from sql import SqlDb` | `from proxy.sql import SqlDb` |
| `from sql.table import Table` | `from proxy.sql import Table` |
| `from sql.column import Column, Columns` | `from proxy.sql import Column, Columns` |
| `from sql.column import String, Integer, Timestamp` | `from proxy.sql import String, Integer, Timestamp` |
| `from storage import StorageManager` | `from proxy.storage import StorageManager` |
| `from tools.encryption import encrypt_value` | `from proxy.encryption import EncryptionManager` |

## Fase 6: Aggiornare le Entities (Tabelle)

### Tabelle che esistono in proxy

Se una tabella esiste già in proxy (tenants, instance, command_log, storages, accounts), **ereditare e aggiungere solo le colonne mancanti**:

#### Prima (tabella duplicata)

```python
from sql import Table, String, Integer

class TenantsTable(Table):
    name = "tenants"
    pkey = "id"

    def configure(self):
        c = self.columns
        c.column("id", String)
        c.column("name", String)
        c.column("active", Integer, default=1)
        # ... tutte le colonne duplicate
        c.column("my_custom_field", String)  # campo specifico
```

#### Dopo (ereditare da proxy)

```python
from proxy.entities.tenant.table import TenantsTable as ProxyTenantsTable
from proxy.sql import String

class TenantsTable(ProxyTenantsTable):
    """Estende TenantsTable di proxy con campi specifici."""

    def configure(self) -> None:
        super().configure()  # Configura tutte le colonne base
        c = self.columns
        # Aggiungere SOLO le colonne specifiche del progetto
        c.column("my_custom_field", String)
```

### Tabelle che NON esistono in proxy

Se la tabella è specifica del progetto, ereditare direttamente da `Table`:

```python
from proxy.sql import Table, String, Integer, Timestamp

class MyCustomTable(Table):
    name = "my_custom"
    pkey = "id"

    def configure(self) -> None:
        c = self.columns
        c.column("id", String)
        # ... tutte le colonne
```

### Entities che NON servono nel progetto

Se una entity proxy va bene così com'è e non richiede modifiche, **NON crearla nel progetto**. ProxyBase la scoprirà automaticamente dai suoi `entity_packages`.

**Rimuovere** le cartelle entities duplicate:

```bash
# Se instance, command_log, storage sono identici a proxy
rm -rf src/core/<project>/entities/instance/
rm -rf src/core/<project>/entities/command_log/
rm -rf src/core/<project>/entities/storage/
```

ProxyBase ha i suoi `entity_packages` di default che includono le entities base. Il tuo progetto specifica solo `entity_packages` per le entities **specifiche**.

## Fase 6b: Aggiornare gli Endpoint

Gli endpoint seguono lo stesso principio delle tabelle: ereditare da proxy e sovrascrivere solo i metodi necessari.

### Endpoint che esistono in proxy

Se un endpoint esiste in proxy (tenants, instance, storages, etc.), **ereditare e sovrascrivere solo i metodi che cambiano**:

#### Prima (endpoint duplicato)

```python
from proxy.interface.endpoint_base import POST, BaseEndpoint

class TenantEndpoint(BaseEndpoint):
    name = "tenants"

    # ❌ DUPLICATO - questi metodi esistono già in proxy
    async def get(self, tenant_id: str) -> dict:
        ...

    async def list(self, active_only: bool = False) -> list[dict]:
        ...

    @POST
    async def delete(self, tenant_id: str) -> int:
        ...

    # ✅ Metodo specifico del progetto
    @POST
    async def add(self, id: str, my_custom_field: str = None, ...) -> dict:
        ...
```

#### Dopo (ereditare da proxy)

```python
from proxy.entities.tenant.endpoint import TenantEndpoint as ProxyTenantEndpoint
from proxy.interface.endpoint_base import POST

class TenantEndpoint(ProxyTenantEndpoint):
    """Estende TenantEndpoint di proxy con campi specifici."""

    # get(), list(), delete() sono EREDITATI - non duplicarli!

    # Sovrascrivere SOLO i metodi che hanno parametri diversi
    @POST
    async def add(
        self,
        id: str,
        name: str | None = None,
        my_custom_field: str = "default",  # campo specifico
        # ... altri campi proxy ...
        active: bool = True,
    ) -> dict:
        async with self.table.record_to_update(id, insert_missing=True) as rec:
            if name is not None:
                rec["name"] = name
            rec["my_custom_field"] = my_custom_field
            rec["active"] = 1 if active else 0
        return await self.get(id)

    # Aggiungere metodi che NON esistono in proxy
    @POST
    async def my_custom_method(self, tenant_id: str) -> dict:
        ...
```

### Endpoint specifici del progetto

Se l'endpoint è 100% specifico del progetto, ereditare da `BaseEndpoint`:

```python
from proxy.interface.endpoint_base import POST, BaseEndpoint

class WopiSessionEndpoint(BaseEndpoint):
    name = "wopi_sessions"  # nome univoco, non presente in proxy

    def __init__(self, table):
        super().__init__(table)

    @POST
    async def create(self, ...) -> dict:
        ...

    async def list(self, ...) -> list[dict]:
        ...
```

### Naming Convention per Entities Specifiche

Per evitare conflitti con entities proxy, usare un prefisso nel nome:

| Tipo | Esempio Proxy | Esempio Progetto |
|------|--------------|------------------|
| Tabella | `sessions` | `wopi_sessions` |
| Classe Table | `SessionsTable` | `WopiSessionsTable` |
| Classe Endpoint | `SessionEndpoint` | `WopiSessionEndpoint` |
| Cartella | `session/` | `wopi_session/` |

## Fase 7: Aggiornare le API delle Tabelle

### Differenze API Critiche

#### Connessione al Database

```python
# ❌ PRIMA - metodo connect/close
await db.connect()
# ... operazioni
await db.close()

# ✅ DOPO - context manager
async with db.connection():
    # ... operazioni
```

#### Upsert (insert or update)

```python
# ❌ PRIMA - record con insert_missing
record = await table.record(pk_value, insert_missing=True)
record["field"] = "value"
await table.update(record)

# ✅ DOPO - record_to_update context manager
async with table.record_to_update(pk_value, insert_missing=True) as rec:
    rec["field"] = "value"
# Salvataggio automatico all'uscita dal context
```

#### Select singolo record

```python
# ❌ PRIMA - select_one
record = await table.select_one(where={"field": "value"})

# ✅ DOPO - record con ignore_missing
record = await table.record(where={"field": "value"}, ignore_missing=True)
# Ritorna {} se non trovato (non None)
```

#### Accesso al database da Table

```python
# ❌ PRIMA - via adapter
await self.db.adapter.execute(sql, params)
row = await self.db.adapter.fetch_one(sql, params)

# ✅ DOPO - direttamente su db
await self.db.execute(sql, params)
row = await self.db.fetch_one(sql, params)
```

#### Parametri SQL

```python
# ❌ PRIMA - placeholder ?
sql = "SELECT * FROM table WHERE id = ?"
params = (id_value,)

# ✅ DOPO - named parameters con :
sql = "SELECT * FROM table WHERE id = :id"
params = {"id": id_value}
```

## Fase 8: Aggiornare i Test

### Pattern delle Fixture in Proxy

genro-proxy usa un pattern specifico per i test:

#### 1. Fixture centrale per database (`tests/sql/conftest.py`)

```python
@pytest_asyncio.fixture
async def sqlite_db() -> AsyncGenerator[SqlDb, None]:
    """Create a SQLite database for testing.

    Opens a connection that stays active for the entire test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SqlDb(db_path)
        async with db.connection():  # ← Connessione aperta durante tutto il test
            yield db
        await db.shutdown()
```

**Punto chiave**: Il `yield db` avviene DENTRO il context manager `async with db.connection()`. La connessione rimane attiva per tutta la durata del test.

#### 2. Import della fixture nelle entities (`tests/proxy/entities/*/conftest.py`)

```python
# Import fixture from sql conftest to make it available here
from tests.sql.conftest import sqlite_db  # noqa: F401
```

#### 3. Fixture per la tabella specifica (`test_table.py`)

```python
@pytest_asyncio.fixture
async def tenant_table(sqlite_db: SqlDb) -> TenantsTable:
    """Create a TenantsTable with SQLite for testing."""
    table = TenantsTable(sqlite_db)
    await table.create_schema()
    return table
```

### Adattare i Test del Progetto

#### Opzione A: Usare SqlDb direttamente (come proxy)

```python
# conftest.py
import tempfile
import pytest_asyncio
from proxy.sql import SqlDb

@pytest_asyncio.fixture
async def sqlite_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SqlDb(db_path)
        async with db.connection():
            yield db
        await db.shutdown()

# test_table.py
from my_project.entities.my_table import MyTable

@pytest_asyncio.fixture
async def my_table(sqlite_db):
    table = MyTable(sqlite_db)
    await table.create_schema()
    return table
```

#### Opzione B: Usare il Server (se serve inizializzazione completa)

```python
# conftest.py
@pytest_asyncio.fixture
async def server(tmp_path):
    server = MyServer(MyConfig(db_path=str(tmp_path / "test.db")))
    await server.init()
    async with server.db.connection():  # ← CRITICO: connection dentro il yield
        yield server
    await server.shutdown()

# test_table.py
@pytest_asyncio.fixture
async def my_table(server):
    return server.db.table("my_table")
```

### Errore Comune: "No active connection"

```
RuntimeError: No active connection. Use 'async with db.connection():'
```

**Causa**: Il `yield` avviene FUORI dal context manager della connessione.

```python
# ❌ SBAGLIATO - yield fuori dal context
@pytest_asyncio.fixture
async def db(tmp_path):
    server = MyServer(config)
    await server.init()
    yield server.db       # ← Connessione già chiusa qui!
    await server.shutdown()

# ✅ CORRETTO - yield dentro il context
@pytest_asyncio.fixture
async def db(tmp_path):
    server = MyServer(config)
    await server.init()
    async with server.db.connection():
        yield server.db   # ← Connessione attiva
    await server.shutdown()
```

### Verificare i pattern nei test di proxy

Prima di scrivere test, controllare come sono fatti in genro-proxy:
- `tests/sql/conftest.py` - fixture centrale `sqlite_db` e `pg_db`
- `tests/proxy/entities/*/conftest.py` - import delle fixture
- `tests/proxy/entities/*/test_table.py` - pattern per testare tabelle

## Fase 9: Riorganizzare la Struttura del Package

### Convenzione dei Nomi Package

genro-proxy ha rinominato il package interno da `proxy` a `genro_proxy`. Tutti i progetti devono seguire questa convenzione:

| PyPI name | Package name | Import |
|-----------|--------------|--------|
| `genro-proxy` | `genro_proxy` | `from genro_proxy import ProxyBase` |
| `genro-wopi` | `genro_wopi` | `from genro_wopi import WopiProxy` |
| `genro-mail` | `genro_mail` | `from genro_mail import MailProxy` |

### Struttura Prima (frammentata)

```
src/
├── core/my_server/       # Codice principale
│   ├── entities/
│   └── ...
├── tools/                # Utilities
└── genro_myproject/      # Quasi vuoto, solo __init__.py
```

### Struttura Dopo (consolidata)

```
src/
└── genro_myproject/      # Unico package
    ├── __init__.py       # Exports principali
    ├── wopi_proxy.py     # Config + Proxy (tutto insieme)
    ├── server.py         # Entry point ASGI
    ├── entities/
    │   ├── tenant/
    │   └── my_entity/
    └── http_client/      # Utilities specifiche
```

### Passi per la Riorganizzazione

#### 1. Spostare il contenuto

```bash
# Copiare contenuto di core/my_server/ in genro_myproject/
cp core/my_server/*.py src/genro_myproject/
cp -r core/my_server/entities src/genro_myproject/
cp -r core/my_server/templates src/genro_myproject/  # se presente

# Spostare tools specifici
cp -r tools/http_client src/genro_myproject/
```

#### 2. Consolidare i moduli

Invece di 3 file separati (config, base, proxy), consolidare in un unico file `my_proxy.py`:

```python
# genro_myproject/my_proxy.py
from dataclasses import dataclass
from genro_proxy.proxy_base import ProxyBase, ProxyConfigBase

@dataclass
class MyConfig(ProxyConfigBase):
    """Configurazione specifica."""
    my_custom_field: str = "default"

def my_config_from_env() -> MyConfig:
    """Factory da environment variables."""
    return MyConfig(
        db_path=os.environ.get("MY_DB", "/data/my.db"),
        # ...
    )

class MyProxy(ProxyBase):
    """Proxy principale."""
    entity_packages = ["genro_myproject.entities"]
    # ...
```

#### 3. Aggiornare __init__.py

```python
# genro_myproject/__init__.py
from .my_proxy import MyConfig, MyProxy, my_config_from_env

__all__ = ["MyConfig", "MyProxy", "my_config_from_env", "main"]

def main() -> None:
    proxy = MyProxy()
    proxy.cli()()
```

#### 4. Aggiornare server.py

```python
# genro_myproject/server.py
from .my_proxy import MyProxy, my_config_from_env

_proxy = MyProxy(config=my_config_from_env())
app = _proxy.api.app
```

#### 5. Aggiornare pyproject.toml

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/genro_myproject"]  # Solo un package

[project.scripts]
my-proxy = "genro_myproject:main"

[tool.ruff.lint.isort]
known-first-party = ["genro_myproject"]
known-third-party = ["genro_proxy"]
```

#### 6. Aggiornare tutti gli import

```python
# Prima
from proxy.sql import Table
from core.my_server import MyConfig

# Dopo
from genro_proxy.sql import Table
from genro_myproject import MyConfig
```

#### 7. Rimuovere cartelle obsolete

```bash
rm -rf src/core/
rm -rf src/tools/
```

#### 8. Spostare i test

```bash
# Struttura test allineata al package
mkdir -p tests/genro_myproject/entities/
mv tests/core/my_server/* tests/genro_myproject/
rm -rf tests/core/
```

### entity_packages con Nuovo Nome

Aggiornare `entity_packages` per riflettere il nuovo path:

```python
# Prima
entity_packages = ["core.my_server.entities"]

# Dopo
entity_packages = ["genro_myproject.entities"]
```

## Checklist di Migrazione

- [ ] Aggiunta dipendenza genro-proxy in pyproject.toml
- [ ] Rimosse cartelle duplicate (sql/, storage/, interface/)
- [ ] Rimossi file duplicati (encryption.py, repl.py)
- [ ] Aggiornata classe Config per estendere ProxyConfigBase
- [ ] Aggiornata classe ServerBase per ereditare da ProxyBase
- [ ] Aggiornati import in tutti i file
- [ ] Tabelle esistenti in proxy: ereditate e aggiunte solo colonne specifiche
- [ ] Tabelle specifiche: aggiornati import da genro_proxy.sql
- [ ] API aggiornate: connection(), record_to_update(), named params
- [ ] Riorganizzata struttura: un solo package `genro_<project>`
- [ ] Consolidati config/base/proxy in un unico file
- [ ] Aggiornato pyproject.toml con nuovo package
- [ ] Test spostati nella nuova struttura
- [ ] Tutti i test passano

## Note Importanti

1. **Metodi nelle Tabelle vs Endpoint**: Molti metodi che sembrano di tabella (es. `list_all()`, `add()`) sono in realtà negli endpoint. Verificare sempre dove si trova il metodo prima di usarlo.

2. **Entity Discovery**: ProxyBase scopre automaticamente le tabelle dai package specificati in `entity_packages`. Non serve registrarle manualmente.

3. **Transazioni**: Il context manager `db.connection()` gestisce le transazioni. Usare `async with db.connection():` per operazioni che devono essere atomiche.

4. **Encryption**: L'EncryptionManager è disponibile via `self.encryption` nella classe server. Le colonne con `encrypted=True` vengono cifrate/decifrate automaticamente.
