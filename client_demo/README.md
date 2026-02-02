# WOPI Demo Client

SPA minimale per testare l'integrazione WOPI con Collabora Online.

## Avvio rapido con Docker Compose

```bash
cd client_demo

# Avvia tutti i servizi (PostgreSQL, MinIO, Collabora)
docker compose up -d

# Aspetta che Collabora sia pronto (può richiedere 30-60 secondi)
docker compose logs -f collabora
# Ctrl+C quando vedi "Ready to accept connections"

# Avvia genro-wopi (dal terminale principale)
cd ..
wopi-proxy serve --port 8080 --db postgresql://wopi:wopi@localhost:5433/wopi

# Servi la demo
python -m http.server 3000 -d client_demo
```

Apri **http://localhost:3000** nel browser.

## Servizi Docker

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| PostgreSQL | 5433 | Database wopi |
| MinIO API | 9002 | S3-compatible storage |
| MinIO Console | 9003 | Web UI (minioadmin/minioadmin) |
| Collabora | 9980 | Document editor |

## Configurazione storage MinIO

Dopo l'avvio, registra lo storage in genro-wopi:

```bash
curl -X POST http://localhost:8080/storages/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "name": "documents",
    "protocol": "s3",
    "endpoint_url": "http://localhost:9002",
    "bucket": "wopi-docs",
    "access_key": "minioadmin",
    "secret_key": "minioadmin"
  }'
```

## Cleanup

```bash
cd client_demo
docker compose down -v  # -v rimuove anche i volumi
```

## Architettura WOPI

```
┌─────────────────┐     REST API      ┌─────────────────┐     WOPI Protocol    ┌─────────────────┐
│   Demo Client   │ ───────────────► │   genro-wopi    │ ◄──────────────────► │   Collabora     │
│   (browser)     │                   │   (proxy)       │                       │   Online        │
└─────────────────┘                   └─────────────────┘                       └─────────────────┘
        │                                     │
        │  iframe con editor                  │
        └─────────────────────────────────────┼───────────────────────────────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Storage   │
                                       │  (S3/local) │
                                       └─────────────┘
```

## Flusso: Aprire un documento

1. **Client** chiama `POST /sessions/create` con:
   - `storage_name`: nome dello storage
   - `file_path`: percorso del file
   - `permissions`: `["view", "edit"]`
   - `account`: identificativo per audit

2. **genro-wopi** crea una sessione e ritorna:
   - `session_id`: ID sessione
   - `file_id`: ID file per WOPI (opaco per Collabora)
   - `access_token`: token di accesso
   - `expires_at`: scadenza sessione

3. **Client** costruisce l'URL per l'iframe:
   ```
   {collabora_url}/browser/dist/cool.html?WOPISrc={wopi_src}&access_token={token}
   ```
   Dove `wopi_src` è URL-encoded: `{wopi_proxy_url}/wopi/files/{file_id}`

4. **Collabora** carica l'editor nell'iframe e chiama:
   - `GET /wopi/files/{file_id}` → CheckFileInfo (metadati file)
   - `GET /wopi/files/{file_id}/contents` → GetFile (contenuto)

## Flusso: Creare un nuovo documento

1. **Client** chiama `POST /storages/create_file` per creare un file vuoto o da template
2. Poi segue il flusso normale di apertura

**Nota**: Collabora non crea file - riceve sempre un file esistente (anche se vuoto).
Per i "nuovi documenti", genro-wopi crea un file vuoto dal template appropriato.

## Flusso: Salvare un documento

Il salvataggio è **automatico** e gestito da Collabora:

1. **Utente** modifica il documento
2. **Collabora** chiama `POST /wopi/files/{file_id}/contents` con il contenuto aggiornato
3. **genro-wopi** salva il file nello storage

### Salvataggio esplicito (da host)

L'host può richiedere un salvataggio via postMessage:

```javascript
iframe.contentWindow.postMessage(JSON.stringify({
    MessageId: 'Action_Save',
    Values: {
        DontTerminateEdit: true,
        DontSaveIfUnmodified: true,
        Notify: true
    }
}), collaboraUrl);
```

## PostMessage API

Comunicazione bidirezionale tra host e Collabora:

### Host → Collabora

| Message | Descrizione |
|---------|-------------|
| `Host_PostmessageReady` | Host pronto a ricevere messaggi |
| `Action_Save` | Richiede salvataggio |
| `Action_Close` | Chiude il documento |

### Collabora → Host

| Message | Descrizione |
|---------|-------------|
| `App_LoadingStatus` | Stato caricamento (Document_Loaded) |
| `Doc_ModifiedStatus` | Documento modificato (true/false) |
| `UI_Save` | Utente ha cliccato "Salva" |
| `Action_Save_Resp` | Risposta al salvataggio |

## Configurazione

Modifica le URL in `index.html`:

```javascript
const CONFIG = {
    wopiProxyUrl: 'http://localhost:8080',  // genro-wopi server
    collaboraUrl: 'http://localhost:9980',   // Collabora Online
};
```

## WOPI Protocol Endpoints

Implementati da genro-wopi:

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/wopi/files/{id}` | GET | CheckFileInfo - metadati file |
| `/wopi/files/{id}/contents` | GET | GetFile - scarica contenuto |
| `/wopi/files/{id}/contents` | POST | PutFile - salva contenuto |
| `/wopi/files/{id}` | POST | Lock/Unlock operations |

## Riferimenti

- [Collabora SDK](https://sdk.collaboraonline.com/)
- [PostMessage API](https://sdk.collaboraonline.com/docs/postmessage_api.html)
- [WOPI Protocol](https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/)
- [cs3org/wopiserver](https://github.com/cs3org/wopiserver) - Implementazione Python di riferimento
