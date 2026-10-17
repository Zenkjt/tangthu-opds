# Phase 10 — Google Drive EPUB Upload Adapter (Checkpoint)

Date: 2026-10-17

## Inspected architecture
- Target folder ID from user: `1hR0H-wZejPM59ka-340atSlJCCYaaUbs`.
- `tangthu-opds` already has the folder registered as branch `Zenkjt - đang đọc`.
- OPDS uses Google Drive API key for read/indexing. API key access is not enough to write files.
- Existing Apps Script `apps-script/Code.gs` handles `check`, `create`, `rename`, and `delete`; there is currently no `upload_epub` action.
- Existing manifest has `drive.readonly`, which must be upgraded to `drive` (or equivalent write scope) for Apps Script to create/update Drive files.

## Implementation in this package
- Adds `src/tangthu_crawler/drive_upload.py` to call a token-protected Apps Script endpoint.
- Pipeline validates EPUB before upload.
- Upload is opt-in via `TANGTHU_UPLOAD_ENABLED`; default false so an un-deployed endpoint cannot break a green crawler build.
- Fixed filename: `0neNews.epub`.
- Required GitHub repository variables/secrets:
  - Variable `TANGTHU_APPS_SCRIPT_URL`: deployed Apps Script Web App `/exec` URL
  - Variable `TANGTHU_NEWS_DRIVE_FOLDER_ID`: `1hR0H-wZejPM59ka-340atSlJCCYaaUbs`
  - Secret `TANGTHU_UPLOAD_TOKEN`: random shared secret, also stored in Apps Script Script Properties as `TANGTHU_UPLOAD_TOKEN`
  - Variable `TANGTHU_UPLOAD_ENABLED`: set to `true` after adding/deploying the upload action
- Upload action must enforce:
  - exact allowlisted target folder ID
  - shared token comparison
  - filename allowlist (`0neNews.epub`, later optionally `0neStory.epub`)
  - update existing same-name file in place; create only if absent
  - set MIME type `application/epub+zip`
- The OAuth manifest must add `https://www.googleapis.com/auth/drive` to Apps Script scopes.
- Redeploy the Web App after updating Code.gs and manifest.

## Status
Uploader client and isolated tests are included. End-to-end upload cannot succeed until the Apps Script server-side action and deployment are updated.
