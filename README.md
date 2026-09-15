# TÀNG THƯ OPDS — v1.0

A small Go-based OPDS catalog and acquisition gateway for books and documents.

TÀNG THƯ is deliberately **file-first**: it indexes filenames and basic file properties instead of becoming an ebook metadata manager.

## v1.0

- Shared Google Drive folders as storage
- Branch registration and independent Branch naming
- Duplicate root-folder detection
- Recursive Drive scan
- Persistent JSON index
- Complete folder hierarchy in Web and OPDS
- Filename and checksum search
- OPDS OpenSearch endpoint
- Real server-mediated OPDS acquisition
- HTTP Range forwarding for reading clients
- Website is catalog-only; it does not expose downloads
- Branch hide/restore
- `online`, `hidden`, `unavailable` states
- Exact uppercase `VN` Branch priority
- Windows 3.x-inspired Web UI
- HTTP Basic Authentication for administration
- Hourly automatic refresh
- Storage Identity Isolation: Drive identifiers and credentials remain server-side

## Acquisition

The public acquisition path is:

```text
Reading app
    ↓
TÀNG THƯ /opds/acquire/<branch-id>/<file-id>
    ↓
TÀNG THƯ server
    ↓
Google Drive API
    ↓
stream
    ↓
Reading app
```

TÀNG THƯ never redirects the reader to a Google Drive `webContentLink`.

The acquisition handler first checks that the requested file exists in the selected online Branch's local index. The Google Drive file ID is then used only internally to stream the object.

## Search

Web:

```text
/search?q=...
```

OPDS:

```text
/opds/search?q=...
```

The search is performed against the persistent local index. A query matches either filename or Drive MD5 checksum.

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
TANGTHU_LISTEN=127.0.0.1:8080
```

Never commit the API key or admin password.

## Run

```sh
go test ./...
go build -o tangthu-opds ./cmd/tangthu
./tangthu-opds
```

Default listen address:

```text
http://127.0.0.1:8080
```

## Data

```text
data/catalog.json
```

Google Drive remains the source of truth. The JSON file is an index/cache, not a storage replacement.

## Architecture

```text
Google Drive shared folders
          ↓
Google Drive adapter
          ↓
Recursive scanner
          ↓
Persistent lightweight index
          ├── Web catalog/search
          └── OPDS catalog/search
                    ↓
             acquisition gateway
                    ↓
             Google Drive stream
```

The MVP intentionally does not require EPUB/OPF parsing, Calibre, OAuth/private Drive, OneDrive, Dropbox, S3, WebDAV, branch daemons, reverse tunnels, or a separate metadata database.

See `TANGTHU_DESIGN.md` for the locked architecture and `V1.0_IMPLEMENTATION.md` for the v1.0 completion record.
