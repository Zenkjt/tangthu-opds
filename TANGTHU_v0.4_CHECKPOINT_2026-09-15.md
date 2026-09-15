# TÀNG THƯ OPDS — v0.4 Checkpoint

**Date:** 2026-09-15  
**Repository:** `https://github.com/Zenkjt/tangthu-opds`  
**Branch:** `main`

## 1. Checkpoint status

**v0.4 is DONE / PASS.**

Google Drive → Scanner → Persistent Index → OPDS navigation has been tested successfully.

Verified:
- Register Branch: PASS
- Shared Google Drive folder validation: PASS
- Retrieve real Drive folder name: PASS
- Independent Branch display name: PASS
- Initial recursive scan: PASS
- Persistent `data/catalog.json`: PASS
- Folder hierarchy preservation using `parent_id`: PASS
- OPDS root → Branch: PASS
- OPDS Branch → child folder: PASS
- OPDS child folder → file: PASS
- Acquisition link generation: PASS (actual acquisition still placeholder)

## 2. Test source

Drive folder ID:
`1jbUFnfzkseLrcWISBwaKwoJK6hZY6bl7`

Actual Drive folder name:
`XteinkX4 optimizePub`

Registered Branch:
- Branch ID: `d048bdebe1f4`
- Display name: `X4 OptimizePub`
- Drive folder name: `XteinkX4 optimizePub`
- Status: `online`

Test child folder:
- Name: `test`
- Folder ID: `1YBXUyiUaVh7plW9HiZ8JWTBjIp2NipEU`

Test file:
- Name: `Copy of Tam-ly-hoc-dam-dong-Gustave-Le-Bon.azw3`
- Drive file ID: `16nxnXugbM7nZz7pkZimROUSlEiqtXe3i`

## 3. Final recursive navigation test

Command:

```bash
curl -s http://127.0.0.1:8080/opds/folder/d048bdebe1f4/1YBXUyiUaVh7plW9HiZ8JWTBjIp2NipEU
```

Returned the expected OPDS file entry with an acquisition link.

Therefore:

**Recursive Drive → Index → OPDS navigation = PASS**

Tested path:

```text
Google Drive
    ↓
Branch scanner
    ↓
Persistent catalog/index
    ↓
OPDS root
    ↓
Branch
    ↓
Folder
    ↓
File
```

## 4. v0.4 acquisition limitation

The acquisition endpoint is still a placeholder.

Current generated form is:

```text
/opds/acquire/<folder-id>/<file-id>
```

For v0.5 it should become:

```text
/opds/acquire/<branch-id>/<file-id>
```

Resolution:

```text
Branch ID
    ↓
Indexed file
    ↓
Google Drive File ID
    ↓
Google Drive API
    ↓
stream file to OPDS client
```

**Do NOT redirect clients to Google Drive `webContentLink`.**

Public clients must never receive Drive URLs, folder IDs, API keys, credentials, OAuth tokens, or other storage identity.

## 5. v0.5 next session

Do not revisit the passing scanner/navigation unless a regression appears.

### v0.5-A — Search

Implement search against the local persistent index:
- filename search
- checksum search
- combined search
- no Google Drive scan per search request

### v0.5-B — Complete recursive OPDS navigation

Keep arbitrary folder depth supported.

```text
TÀNG THƯ
└── Branch
    ├── files
    └── Folder
        └── Subfolder
            └── files
```

### v0.5-C — Acquisition Gateway

Implement real server-mediated acquisition:

```text
Reading app
    ↓
Tàng Thư OPDS acquisition URL
    ↓
Tàng Thư server
    ↓
Google Drive API
    ↓
stream file
    ↓
Reading app
```

Requirements:
- no Drive redirect
- server-side validation of Branch/file relationship
- Google Drive API retrieval
- stream response to client
- preserve Storage Identity Isolation
- later: short-lived acquisition tokens, rate limiting, logging, abuse protection

## 6. Architecture to preserve

Storage abstraction:

```go
type Storage interface {
    List(...)
    Stat(...)
    Open(...)
}
```

MVP implementation:
`GoogleDriveSharedStorage`

Pipeline:

```text
Google Drive
     ↓
Scanner
     ↓
Lightweight persistent Index
     ↓
OPDS / Web
```

Do not introduce for MVP:
- branch daemon
- reverse WebSocket tunnel
- heartbeat
- mirror network
- quarantine/mirror
- local branch HTTP
- EPUB/OPF metadata pipeline
- ISBN extraction
- Calibre DB
- OAuth/private Drive
- OneDrive/Dropbox/S3/WebDAV/local filesystem

## 7. Next-session rule

**Freeze v0.4.**

Start v0.5 from the current GitHub `main` state. First inspect the current `main` code, then implement Search and Acquisition incrementally rather than rewriting the scanner.
