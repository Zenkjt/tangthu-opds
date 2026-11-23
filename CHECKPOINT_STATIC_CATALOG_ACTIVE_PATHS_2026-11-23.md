# CHECKPOINT — Static catalog stats: active workflow paths
**Date:** 2026-11-23

## Root cause
Commit `1690f1c` modified root-level duplicates (`main.go`, `catalog_shards_test.go`, `postprocess_bookshelf.py`, `resolve_build_mode.py`, `tangthu_lifecycle.py`). The active Cloudflare workflow does not invoke those files. `.github/workflows/cloudflare.yml` invokes:
- `go run ./cmd/generate` → `cmd/generate/main.go`
- `scripts/resolve_build_mode.py`
- `scripts/tangthu_lifecycle.py`
- `scripts/postprocess_bookshelf.py`

Therefore the previous commit did not update the code used by the Pages build.

## Patch contents
- `cmd/generate/main.go`: per-shelf `book_count`, `font_count`, `format_counts`; incremental mode requires complete stats schema; R2 snapshot manifest must have `complete:true`.
- `cmd/generate/catalog_shards_test.go`: stats, incremental preservation, and complete-snapshot tests.
- `scripts/postprocess_bookshelf.py`: shelf cards and footer read catalog metadata; no `loadAllFiles()` for initial shelf stats/footer.
- `scripts/resolve_build_mode.py`: force full build when catalog stats schema is absent.
- `scripts/tangthu_lifecycle.py`: suspended shelves retain the same stats schema with zero values.

## Deployment
Replace only the five files above using the exact paths. The root-level duplicates are not part of this patch. Keep `DrivePriorityV4.gs` unchanged.
