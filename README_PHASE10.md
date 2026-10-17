# Phase 10 — Drive upload

This ZIP adds the crawler-side upload adapter. It deliberately defaults to upload disabled until the matching Apps Script server-side upload action is installed and deployed.

Required repo configuration:
- Actions variable `TANGTHU_APPS_SCRIPT_URL`: Apps Script deployed `/exec` URL (not the editor project URL).
- Actions variable `TANGTHU_NEWS_DRIVE_FOLDER_ID`: `1hR0H-wZejPM59ka-340atSlJCCYaaUbs`.
- Actions secret `TANGTHU_UPLOAD_TOKEN`: random shared secret; set same value in Apps Script Script Properties.
- Actions variable `TANGTHU_UPLOAD_ENABLED`: `true` only after the endpoint is deployed.

The existing Apps Script project needs a Drive write scope and an `upload_epub` POST action. That action should only allow the fixed target folder, validate token and filename, and update `0neNews.epub` in place by file ID.
