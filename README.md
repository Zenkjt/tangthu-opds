# TÀNG THƯ OPDS — GitHub Pages / $0

TÀNG THƯ is a lightweight multi-branch OPDS catalog for books and documents.
It is deliberately **file-first**: it indexes filenames and basic file properties instead of becoming an ebook metadata manager.

## Current deployment model

TÀNG THƯ now targets a **GitHub-only, $0 runtime architecture**:

```text
Google Drive shared folders
        ↓
GitHub Actions — hourly/manual
        ↓
Go static generator
        ↓
GitHub Pages
   ┌────┴────┐
   Web      OPDS
              ↓
       Xteink X4 / reader
              ↓
       Google Drive download
```

No VPS, Cloud Run, Railway, database, or always-on Go server is required.

The existing Go server in `cmd/tangthu` remains useful as the earlier server-mediated prototype and for local development/reference. The GitHub Pages workflow uses `cmd/generate` instead.

## Storage

MVP storage is **shared Google Drive folders**.

Each Branch stores:

- Branch ID
- Branch display name
- Google Drive root folder ID
- enabled state

The Google Drive folder name and Branch display name are independent.

## Dedicated Google Account

Contributors are strongly encouraged to use a **dedicated Google Account for TÀNG THƯ**, not their personal/main Google Account.

For a public $0 OPDS library, the Drive files/folders used by the library need to be accessible to the reading client. The exact sharing policy should therefore be chosen deliberately.

## Privacy trade-off in the $0 architecture

The public Web catalog does not provide a Google Drive download button.

However, GitHub Pages is static and cannot proxy a download request. Therefore an OPDS acquisition entry must ultimately contain a Google Drive download URL. A client or user inspecting the OPDS XML can recover the Drive file ID.

This is an intentional trade-off to keep the runtime completely free. A dedicated TÀNG THƯ Google Account reduces the impact of exposing a file ID, but does not make the Drive URL secret.

## Branch ordering

Branches whose display name begins exactly with uppercase `VN` are listed first, followed alphabetically by all other Branches.

## Recursive hierarchy

Google Drive folder hierarchy is preserved:

```text
Branch
 ├── Folder
 │    ├── Subfolder
 │    │    └── Book.pdf
 │    └── Book.epub
 └── Other Book.azw3
```

The same hierarchy is generated into OPDS.

## Supported file information

The generated index contains:

- filename
- MIME type
- size
- modified time
- Drive MD5 checksum when available
- folder relationship
- Drive file ID

No EPUB/OPF, ISBN, Calibre, author, publisher, series, or cover database is required.

## GitHub Actions

Workflow:

```text
.github/workflows/pages.yml
```

It runs:

- hourly
- manually with `workflow_dispatch`
- after relevant source/config changes on `main`

Required repository secret:

```text
TANGTHU_GOOGLE_API_KEY
```

Branch configuration:

```text
config/branches.json
```

Example:

```json
{
  "branches": [
    {
      "id": "d048bdebe1f4",
      "display_name": "X4 OptimizePub",
      "root_folder_id": "YOUR_GOOGLE_DRIVE_FOLDER_ID",
      "enabled": true
    }
  ]
}
```

## GitHub Pages setup

In the repository:

**Settings → Pages → Build and deployment → Source: GitHub Actions**

The default project URL is:

```text
https://zenkjt.github.io/tangthu-opds/
```

OPDS root:

```text
https://zenkjt.github.io/tangthu-opds/opds/index.xml
```

## First real-device test

The first test is deliberately simple:

1. Open the OPDS root on Xteink X4.
2. Enter `X4 OptimizePub`.
3. Navigate into `test`.
4. Select `Copy of Tam-ly-hoc-dam-dong-Gustave-Le-Bon.azw3`.
5. Verify download starts.
6. Verify the resulting file opens correctly.
7. Test interruption/resume if the X4 reader supports resume.

This test determines whether the Google Drive direct-download endpoint is suitable as the acquisition endpoint for X4.

## Earlier server prototype

`cmd/tangthu` contains the v1.0 server-mediated prototype. It demonstrated:

- recursive Drive scan
- persistent JSON index
- OPDS navigation
- server-side acquisition
- HTTP Range forwarding
- Web catalog
- Branch registration and hide/restore

That prototype required a live Go server. The GitHub Pages architecture intentionally removes that runtime dependency.
