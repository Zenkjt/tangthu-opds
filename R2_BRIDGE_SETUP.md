# Tàng Thư — R2 bridge build

This repository is based on the current working baseline's application scripts and UI post-processors, with the R2 snapshot generator and dynamic OPDS Worker bridge retained.

## Data flow

1. Google Apps Script (`apps-script/DrivePriorityV4.gs`) scans Drive and publishes complete snapshot manifests/pages to R2. Its checkpoint and priority-state behavior is unchanged.
2. GitHub Actions runs `cmd/generate`, which reads those R2 snapshots through the storage Worker API.
3. The generator emits the static web catalog (`docs/catalog.json` and per-shelf catalog shards) for Cloudflare Pages.
4. The same generator publishes `opds/branches.json` and `opds/branches/{branch_id}.json` into R2.
5. `worker.js` serves OPDS XML dynamically from those R2 objects. The Pages Functions under `functions/opds*` proxy `/opds` requests to the deployed Worker.

The large static `docs/opds/branch/**` XML tree is intentionally not generated or deployed.

## GitHub Actions settings

Set the following repository settings:

- Variable `TANGTHU_R2_API_URL`: `https://tangthu-storage-api.mienluonngon.workers.dev`
- Secret `TANGTHU_R2_API_TOKEN`: the same bearer token configured as the Worker secret `TANGTHU_API_TOKEN` and Apps Script property `TANGTHU_R2_API_TOKEN`.
- Existing settings used by the baseline workflow remain required where applicable: `TANGTHU_GOOGLE_API_KEY`, `TANGTHU_DOWNLOAD_WORKER_URL`, `TANGTHU_APPS_SCRIPT_URL`, `TANGTHU_STORY_API_URL`, and `TANGTHU_STORY_SOURCES_URL`.

The workflow still uses the baseline shelf lifecycle, UI post-processing, registration, news, story, and shelf-number steps. It does not run the legacy static OPDS URL rewrite or pagination steps because those expect the removed XML tree.

## Worker deployment

Deploy `worker.js` to the existing `tangthu-storage-api` Worker, preserving its existing R2 bucket binding named `BUCKET` and secret `TANGTHU_API_TOKEN`. Do not create a new bucket or delete existing objects. The code supports the existing `snapshots/`, `checkpoints/`, and `opds/` object prefixes. The public OPDS GET endpoints are `/opds/index.xml` and `/opds/branch/{branch_id}/{folder_id}.xml`.

The Pages proxy in `functions/opds.js` and `functions/opds/[[path]].js` targets the existing Worker hostname. If that hostname changes, update the constant in both files.

## Important behavior in this bridge

- Shelf ordering is VN-prefixed first, then alphabetical; shelf numbers remain metadata and are not used as the OPDS ordering key.
- Empty folders serialize their shard list as `[]`, not `null`.
- Web global search and shelf statistics load root-level entries as well as nested folders.
- A stale browser-history folder ID absent from the latest root manifest falls back to the shelf root rather than leaving the catalog unusable.
- R2 snapshots remain the source of truth; no automatic fallback to live Drive scans is introduced.

## Validation performed

Run locally:

```sh
go test ./...
python3 -m py_compile scripts/*.py
node --check worker.js
```

CrossPoint compatibility still requires an end-to-end test on the actual reader after deployment. A browser successfully opening the feed is not treated as proof that CrossPoint can parse and navigate it.
