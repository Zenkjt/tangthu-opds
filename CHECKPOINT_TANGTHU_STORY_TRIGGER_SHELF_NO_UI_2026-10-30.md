# CHECKPOINT TANG THU CROSSPOINT STORY TRIGGER — SHELF NUMBER UI
Date: 2026-10-30

## Decision

CrossPoint Story Controller identifies a user's bookshelf by a stable `shelf_no`.

The bookshelf number is displayed in the Tàng Thư GUI immediately beside the bookshelf name, not beside Reload.

Example:

    TỦ SÁCH #12

`#12` is the stable identifier used by the CrossPoint plugin.

## Architecture

    CrossPoint Plugin
          │
          │ api.relay()
          ▼
    Tàng Thư Apps Script /exec
          │
          │ action = story_trigger
          │ shelf_no + direction
          ▼
    config/branches.json
          │
          ├── shelf_no
          ├── id / user_id
          └── root_folder_id
          │
          ▼
    tangthu-story-worker
          │
          ▼
    tangthu-story-scraper
          │
          ▼
    Google Drive

## Rules

- `shelf_no` is an explicit field in `branches.json`.
- Never derive `shelf_no` from array position.
- Reordering `branches.json` must not change a shelf's number.
- Plugin stores only `shelf_no`.
- Plugin does not store `user_id`, `folder_id`, `story_id`, or `entry_id`.
- Plugin has no direct Drive access.
- Plugin does not call Story Worker directly.
- Apps Script is the single receptor for the plugin.
- Story Worker uses a dedicated `STORY_TRIGGER_TOKEN`.
- Existing `TANGTHU_UPLOAD_TOKEN` and `GITHUB_TOKEN` are not reused for this purpose.

## GUI

Display:

    <shelf display name> #<shelf_no>

The number is part of the shelf identity and should be visible wherever the bookshelf name is presented to the user.

## Implementation order

1. Add explicit `shelf_no` to `config/branches.json`.
2. Pass `shelf_no` through the Go catalog generator into `docs/catalog.json`.
3. Update bookshelf rendering so the number appears beside the shelf name.
4. Add `story_trigger` routing to Apps Script.
5. Add `STORY_TRIGGER_TOKEN` validation and trigger handling in Apps Script / Worker.
6. Build CrossPoint plugin with:
   - shelf number input
   - PREVIOUS
   - NEXT
   - remembered shelf number
   - vertical layout
   - no story title/status display
7. Test end-to-end with one real shelf.

## Important

Do not create a separate Cloudflare Function or a plugin-specific backend.
Do not create a second Story API.
