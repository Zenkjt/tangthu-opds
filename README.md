# TÀNG THƯ OPDS — v0.4

A small Go-based OPDS file catalog for books and documents.

TÀNG THƯ is deliberately **file-first**: it catalogs files and their basic properties rather than trying to become an ebook metadata-management system.

## Current v0.4 implementation

- Shared Google Drive folders as the initial storage backend
- Google Drive folder URL/ID validation
- Registration flow:
  - validate the folder
  - retrieve the real Google Drive folder name
  - choose an independent TÀNG THƯ Branch name
- Duplicate root-folder detection
- Recursive Google Drive scanning
- Complete folder hierarchy preserved in a lightweight JSON index
- Filename, MIME, size, modified time, and Drive MD5 checksum
- Persistent catalog
- Manual Branch refresh
- Automatic refresh approximately every hour
- Branch hide/restore
- `online` / `hidden` / `unavailable` states
- Exact uppercase `VN` Branch priority
- Windows 3.x-inspired Web catalog
- OPDS root -> Branch -> folders/files
- Website does not expose file downloads
- OPDS acquisition URLs are reserved for the server-mediated acquisition step
- Admin endpoints protected by HTTP Basic Authentication

## What v0.4 does not do yet

- Real OPDS acquisition/file streaming
- Search
- OAuth/private Google Drive
- EPUB/OPF metadata extraction
- Cover extraction
- Database storage
- Rate limiting / production abuse protection

## Google Drive requirement

The current adapter uses the Google Drive API with an API key for publicly shared folders. Google documents this flow for folders shared as "Anyone with the link" / public access. Shared-drive folders require the corresponding shared-drive parameters. See the Google Drive API documentation.

Do **not** put the API key in the repository.

## Configuration

Required:

```text
TANGTHU_GOOGLE_API_KEY=...
TANGTHU_ADMIN_PASSWORD=...
```

Optional:

```text
TANGTHU_ADMIN_USER=admin
TANGTHU_DATA_FILE=data/catalog.json
```

Run:

```sh
go test ./...
go build -o tangthu-opds ./cmd/tangthu
./tangthu-opds
```

The server listens on:

```text
http://127.0.0.1:8080
```

## Data model

The persistent catalog is intentionally simple:

```text
data/catalog.json
```

Google Drive remains the source of truth for files. The JSON file is a catalog/index cache, not a replacement storage system.

## Architecture

```text
Google Drive
     |
     v
Google Drive adapter
     |
     v
Recursive scanner
     |
     v
Lightweight JSON index
     |
     +---- Web catalog
     |
     +---- OPDS catalog
     |
     +---- future acquisition gateway
```

## License

This prototype contains an MIT license notice because the implementation is based on an MIT-licensed Mayberry codebase where applicable. See `LICENSE`.

## Design

See [`TANGTHU_DESIGN.md`](TANGTHU_DESIGN.md) for the living architecture and locked MVP decisions.
