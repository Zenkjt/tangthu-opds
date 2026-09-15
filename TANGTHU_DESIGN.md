# TÀNG THƯ OPDS — Living Design Document
Version: 1.1
Date: 2026-09-15

## 1. Product identity

**Name:** TÀNG THƯ OPDS  
**Technical/repository name:** `tangthu-opds`

Tàng Thư OPDS is a lightweight distributed file catalog for books and documents.
It is **not an ebook metadata-management system**.

Core principle:

> Tàng Thư OPDS helps users find files and download them through OPDS; metadata enrichment is optional.

## 2. Storage — MVP

Shared Google Drive folders ONLY.

A Branch points to one shared Google Drive root folder. Contributors do not install software.

Branch registration:
- Branch display name
- Google Drive shared-folder URL
- Validate the root folder
- Scan recursively

No private Google Drive OAuth in MVP.

## 3. Branch model

A Branch is a logical library source, not a daemon.

Conceptual fields:
- id
- display_name
- storage_type = google_drive_shared
- root_folder_id
- enabled
- status
- last_scan
- error/reason when unavailable

### Branch visibility

Admin can **hide** a Branch manually.

Hidden means:
- absent from Web public catalog
- absent from OPDS
- configuration is retained
- Admin can restore it

If the Google Drive root folder disappears, is deleted, or becomes inaccessible:
- Branch becomes `unavailable`
- it is omitted from public Web/OPDS
- its configuration is retained
- Admin sees the reason and can repair/remove it

Do not immediately delete configuration because a temporary API failure may recover.

## 4. OPDS root

Entering OPDS shows Branches immediately.

Example:

TÀNG THƯ
- VN Y Khoa
- VN Văn học
- English Library
- Comics

No extra Mayberry-style hierarchy before Branches.

## 5. Branch ordering

### VN convention

Branches whose display name begins **exactly with uppercase `VN`** are prioritized.

Examples:
- `VN Y Khoa` -> prioritized
- `VN Văn học` -> prioritized
- `vn books` -> not prioritized
- `Vietnam Books` -> not prioritized
- `Vietnamese` -> not prioritized

Within the prioritized group, use normal alphabetical ordering.
All other Branches follow alphabetically.

The Web UI explicitly tells users that `VN`-prefixed libraries are shown first.

## 6. Google Drive folder tree

Scanning is recursive.

Google Drive folder hierarchy = Tàng Thư Branch hierarchy = OPDS navigation hierarchy.

No manual hierarchy maintenance.

Example:

Medical Books/
  Anatomy/
    Gray's Anatomy.pdf
  Surgery/
    General/
      Surgery.pdf
    Plastic/
      Cleft.pdf

appears identically as the Branch navigation tree.

## 7. File-first philosophy

The index stores basic file information:
- file_id
- branch_id
- parent_folder_id
- name
- MIME
- size
- modified time
- Drive-provided checksum when available
- path/tree relationship

Filename is the default OPDS title.

No mandatory EPUB/OPF parsing, ISBN, author, publisher, series, Calibre database, or cover extraction.

## 8. Supported formats

Broad file support, initially including:
EPUB, PDF, MOBI, AZW, AZW3, CBZ, CBR, FB2, TXT, DOC, DOCX, RTF, ZIP, and similar files.

Extension-to-MIME mapping is sufficient.
Unknown files may use `application/octet-stream`.

## 9. Lightweight index

Architecture:

Google Drive -> Scanner -> Lightweight Index -> Catalog/OPDS/Web

Do not scan Google Drive for every request.

Default automatic refresh: approximately every 1 hour.

Also provide manual Refresh Now.

Future intervals may include:
15m / 30m / 1h / 6h / 12h / 24h / manual.

## 10. Duplicate policy

Do not filter, delete, or automatically merge duplicate files.

Same content in two Branches remains two entries.

Checksum is informational and may support future optional duplicate visualization.

## 11. Web UI

Style: simple old-style file manager inspired by Windows 3.x.

Required:
- Branch list
- folder/file tree
- name
- size
- modified date
- MIME
- checksum
- filename search
- checksum search
- both search
- Branch hide/restore
- Branch status
- manual refresh
- root-folder validation/errors

## 12. OPDS and Web consistency

Web and OPDS should use the same catalog tree and sorting policy.

The server controls default ordering.

Clients such as KOReader/X4 normally receive entries in server order, although a client may apply its own presentation sorting.

## 13. Storage abstraction

Conceptually:

type Storage interface {
    List(...)
    Stat(...)
    Open(...)
}

MVP implementation:
`GoogleDriveSharedStorage`

## 14. Removed Mayberry concepts

Do not carry these into MVP:
- reverse WebSocket tunnel
- branch daemon
- heartbeat
- mirror network
- quarantine/mirror machinery
- local branch HTTP server
- EPUB metadata pipeline
- ISBN extraction
- Calibre-style metadata database
- catalog synchronization from daemon

## 15. Architecture

                         TÀNG THƯ OPDS
                              |
              +---------------+---------------+
              |                               |
           Web UI                            OPDS
              |                               |
              +---------------+---------------+
                              |
                         Catalog API
                              |
                       Branch / File Tree
                              |
                       Storage Adapter
                              |
                  Google Drive Shared Folder

## 16. Security

Shared Google Drive permissions determine storage access.

Admin/setup endpoints must be protected before Internet deployment.
HTTPS is required for Internet deployment.

## 17. MVP checklist

1. Register Branch
2. Shared Google Drive folder
3. Validate folder
4. Recursive scan
5. Preserve complete hierarchy
6. Lightweight persistent index
7. OPDS root immediately shows Branches
8. Branch -> folders/files
9. Download/acquisition
10. Broad extension/MIME mapping
11. Filename
12. Size
13. Modified date
14. Checksum
15. Filename search
16. Checksum search
17. Windows-3.x-style Web UI
18. Automatic periodic scan
19. Manual refresh
20. Exact-uppercase-VN Branch priority
21. Web notice explaining VN priority
22. Admin hide/restore Branch
23. Automatically omit unavailable Branches from public Web/OPDS
24. Retain unavailable Branch configuration and error state

## 18. Design principle

> **Tàng Thư OPDS is a distributed file catalog, not an ebook management system.**

It answers:
- Where is the file?
- What is it called?
- What are its basic file properties?
- Can the client download it?

Everything else is optional.

---

## 13. Branch registration and naming

Branch identity is deliberately separated from the Google Drive folder identity.

### Registration flow

```text
REGISTER BRANCH

Google Drive folder link:
[ https://drive.google.com/drive/folders/ABC123 ]

Google Drive folder name:
[ Medical Books ]        <- retrieved automatically, read-only

Branch display name:
[ VN Y Khoa ]            <- editable

[ Save ]
```

The user first provides the Google Drive folder link. Tàng Thư extracts the
folder ID, validates that the folder is accessible, and retrieves the real
Google Drive folder name.

The Drive folder name is only contextual information and an initial suggestion.
It is NOT the Branch identity.

The user chooses the Branch display name. This name is what appears in the
public Web catalog and OPDS.

### Persistent identity

A Branch stores at least:

```text
branch_id
display_name
storage_type = google_drive_shared
root_folder_id
status
```

`root_folder_id` identifies the storage. `display_name` identifies how the
library is presented by Tàng Thư.

Renaming the folder directly in Google Drive must NOT automatically rename the
Branch.

The owner can rename the Branch display name independently at any time.

### Duplicate root-folder detection

When a user registers a folder, Tàng Thư checks whether the same
`root_folder_id` is already registered.

If it is already registered:

```text
This Google Drive folder is already registered.

Current Branch name:
VN Y Khoa

New Branch name:
[ VN Ngoại khoa ]

[ Update ]
```

The system must not create a second Branch pointing to the same root folder
unless a future explicit administrative feature permits it.

---

## 14. Public storage-identity isolation

The Google Drive backend is an implementation detail and must be isolated from
public users.

Public Web and OPDS responses must NOT expose:

- Google account/email
- Google Drive folder URL
- Google Drive folder ID
- Google API key
- OAuth credentials/tokens
- Google Drive `webContentLink`
- other backend storage credentials or identifiers

The public identity is:

```text
TÀNG THƯ
  ↓
Branch display name
  ↓
Tàng Thư folder/file identity
```

not:

```text
TÀNG THƯ
  ↓
Google Drive URL/account
```

This is called **Storage Identity Isolation**.

---

## 15. Web catalog vs OPDS acquisition

The Website and OPDS have deliberately different responsibilities.

### Website

The public Website is a catalog and management interface.

It may provide:

- Branch browsing
- folder/file browsing
- filename search
- checksum search
- file information
- Branch status
- registration
- Branch rename
- Branch hide/restore for authorized users
- refresh/status information

The Website MUST NOT provide file download.

There must be no public Web download button or direct public file-serving route.

### OPDS

OPDS provides:

- catalog navigation
- search
- acquisition links

The normal file acquisition path is:

```text
Reading app
    ↓
Tàng Thư OPDS acquisition URL
    ↓
Tàng Thư server
    ↓
Google Drive API
    ↓
file stream
    ↓
reading app
```

Tàng Thư must NOT simply redirect the client to a Google Drive
`webContentLink`.

This keeps the Google Drive backend hidden and allows Tàng Thư to become the
single acquisition gateway.

### Acquisition security boundary

The acquisition endpoint is the only public path that should serve cataloged
book files.

Future production implementation should support, where appropriate:

- short-lived acquisition tokens
- authorization
- rate limiting
- request logging
- abuse protection
- controlled streaming
- backend error handling

These are separate from the public catalog.

---

## 16. Updated public architecture

```text
                         INTERNET
                            │
                 ┌──────────┴──────────┐
                 │                     │
              WEBSITE                 OPDS
                 │                     │
          catalog / admin       catalog + acquisition
                 │                     │
                 └──────────┬──────────┘
                            │
                       TÀNG THƯ
                            │
                  ┌─────────┴─────────┐
                  │                   │
             Catalog Index       Acquisition Gateway
                  │                   │
                  │             Google Drive API
                  │                   │
                  └─────────┬─────────┘
                            │
                    Shared Google Drive
```

The Website is not a file server.

The OPDS acquisition gateway is the controlled file-serving boundary.

Google Drive remains backend storage and is never exposed as the public
storage identity.

---

## 17. Updated MVP checklist

1. Register Branch
2. Accept shared Google Drive folder link
3. Extract and validate root folder ID
4. Retrieve and display real Google Drive folder name
5. Allow editable Branch display name
6. Detect duplicate registered root folder
7. Allow Branch display-name rename without changing Drive folder
8. Shared Google Drive storage only
9. Recursive scan
10. Preserve complete hierarchy
11. Lightweight persistent index
12. OPDS root immediately shows Branches
13. Branch -> folders/files
14. OPDS acquisition
15. Website catalog only; NO file download
16. Server-side acquisition gateway; do NOT redirect to Google Drive
17. Broad extension/MIME mapping
18. Filename
19. Size
20. Modified date
21. Checksum
22. Filename search
23. Checksum search
24. Windows-3.x-style Web UI
25. Automatic periodic scan
26. Manual refresh
27. Exact-uppercase-`VN` Branch priority
28. Web notice explaining `VN` priority
29. Admin hide/restore Branch
30. Automatically omit unavailable Branches from public Web/OPDS
31. Retain unavailable Branch configuration and error state
32. Storage Identity Isolation
33. Do not expose Google account, Drive URL, Drive ID, API key, OAuth token,
    or Drive webContentLink publicly

---

## 18. Current architectural status

**STATUS: ARCHITECTURE CHOSEN — PROTOTYPE v0.3**

The following decisions are now considered locked for the MVP:

- TÀNG THƯ OPDS is a lightweight multi-branch OPDS file catalog.
- Shared Google Drive folders are the only initial storage provider.
- Branch display name is independent from Google Drive folder name.
- Google Drive folder ID is the storage identity.
- OPDS root shows Branches immediately.
- Folder hierarchy is preserved recursively.
- Website is catalog/management only and does not download files.
- OPDS acquisition is the controlled download path.
- Tàng Thư server mediates acquisition; clients do not receive Google Drive
  download URLs.
- Google Drive account/storage identity is isolated from public users.
- Branches beginning exactly with uppercase `VN` are prioritized.
- Hidden and unavailable Branches are omitted from the public catalog.
- Unavailable Branch configuration is retained for repair.
- No EPUB metadata database is required.
- No duplicate filtering or merging is performed.

These decisions form the baseline for the next implementation phase:
Google Drive adapter -> recursive scanner -> persistent index -> real OPDS
acquisition streaming.
