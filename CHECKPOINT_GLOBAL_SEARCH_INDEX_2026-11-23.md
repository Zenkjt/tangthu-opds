# Checkpoint — Global Search Index

Date: 2026-11-23
Baseline: repository ZIP HEAD `17afbc0d33952bb675ec697c3cb42d8b9658c315`

## Decision

Build a static, per-shelf search/inventory index from the same `Branch.Files` data already loaded by the Generator. Do not add a database, Worker endpoint, scheduled job, or additional Google Drive scan.

## Data layout

- Each shelf has `catalog/<branch-id>/search/0001.json`, `0002.json`, ...
- Each page contains at most 1,000 non-folder records.
- Each record contains the existing catalog file fields plus `path` (folder path relative to shelf root).
- `catalog.json` exposes the page paths as `branches[].search_shards`.

## Update rules

- Full build: `writeCatalogBranchShards` creates directory shards and the search index for every shelf.
- Incremental build: `mergeCatalogShards` calls `writeCatalogBranchShards` only for replacement shelves, so only those shelves' directory and search shards are regenerated. Other shelves remain untouched.
- Index revision follows the shelf's existing catalog revision.
- The progressive R2 snapshot acceptance/publishing behavior is unchanged.

## Consumers

- Website search loads `search_shards` instead of enumerating every directory shard. Results retain filename, MIME, size, modified time, checksum, shelf identity and parent ID. Existing accent-insensitive and fuzzy matching remain.
- TTlistFull (`apps-script/InventoryExport.gs`) reads the same index pages and uses each record's stored `path`; it no longer expands root/directory shards.

## Operational impact

- No new Drive API calls or recurring jobs.
- Additional static JSON storage and some Generator CPU/RAM during full/incremental build.
- Browser search downloads index pages on first search and reuses them in memory for subsequent searches in that page session.
- TTlistFull still downloads the inventory records when explicitly requested, but from the compact index rather than the full directory tree.

## Validation performed

- `go test ./...` passes.
- Added `TestCatalogSearchIndexContainsFilesAndFolderPaths`.
- `node --check` passes for the modified Apps Script file.
- No live Cloudflare Pages deployment or live Apps Script export was executed in this environment.
