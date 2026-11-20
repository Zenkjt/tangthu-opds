# R2 snapshot reader migration

`cmd/generate` now reads shelf snapshots exclusively from the Cloudflare Worker/R2 API.
It no longer searches Google Drive for `TANGTHU_SNAPSHOT_<branch>.json`, downloads Drive snapshot pages, or falls back to a live Google Drive scan.

## GitHub Actions configuration

Set these repository settings:

- Actions variable `TANGTHU_R2_API_URL`: `https://tangthu-storage-api.mienluonngon.workers.dev`
- Actions secret `TANGTHU_R2_API_TOKEN`: the same bearer token configured as the Worker secret `TANGTHU_API_TOKEN` and Apps Script property `TANGTHU_R2_API_TOKEN`.

The workflow passes these values only to the `Generate static catalog from R2 snapshots` step.

The separate shelf-lifecycle preflight still uses `TANGTHU_GOOGLE_API_KEY` to inspect Google Drive shelf metadata. That is not used by the Go Generator to read snapshot contents.

## R2 contract

Manifest key:

`snapshots/{branch_id}/manifest.json`

Expected manifest fields include `version: 2`, `storage: "r2"`, `branch_id`, `generation_id`, `complete: true`, `page_count`, `pages`, and `item_count`.

Each page key must be under:

`snapshots/{branch_id}/generations/{generation_id}/pages/`

The Worker GET endpoint returns the stored JSON object directly. The generator checks the manifest identity/completion, page-key generation boundary, and raw page item count. Missing or incomplete snapshots fail the build; there is deliberately no Google Drive fallback.
