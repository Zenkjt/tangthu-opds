# Checkpoint: Shared incremental OPDS pipeline
Date: 2026-11-09

## Decision
Use one shared GitHub Actions workflow for Refresh and Drive Check.

- `main` stores source code and configuration.
- `site-state` stores only the latest successfully deployed website output.
- Cloudflare Pages remains the hosting/deployment target.
- Refresh and Drive Check both dispatch `drive_changed` with a `client_payload.shelves` list.
- A repository dispatch performs a shelf-scoped update when site-state exists and lifecycle/shelf identity is unchanged.
- Manual and scheduled runs remain full builds.
- Lifecycle transitions, shelf additions/removals, or shelf identity/name changes force a full build.

## Implementation in this patch
1. `cmd/generate/main.go`
   - Reads `TANGTHU_SHELVES`.
   - In incremental mode, scans only selected shelves.
   - Replaces only those shelves' OPDS folder trees.
   - Merges their file lists into the existing `catalog.json`, preserving other shelves and existing metadata.
   - Does not regenerate the website HTML or root OPDS index in incremental mode.
   - Full-build behavior remains the fallback.

2. `scripts/resolve_build_mode.py`
   - Selects `incremental` only for valid repository-dispatch shelf IDs when lifecycle and shelf identity are unchanged.
   - Otherwise selects `full`.

3. `scripts/rewrite_opds_download_urls.py` and `scripts/paginate_opds.py`
   - Accept `TANGTHU_SHELVES`.
   - Limit post-processing to the selected shelf directories in incremental mode.

4. `.github/workflows/cloudflare.yml`
   - Restores `site-state` before building.
   - Uses one workflow for all triggers.
   - Runs global UI post-processors only for full builds.
   - Serializes deployment runs (`cancel-in-progress: false`).
   - Saves `site-state` only after Cloudflare deployment succeeds.
   - The `site-state` branch is recreated with a single latest-state commit to avoid history growth.

## First-run behavior
If `site-state` does not exist, the workflow performs a full build. After successful Cloudflare deployment it creates `site-state` automatically. No manual branch creation is required.

## Validation
- Python syntax checks passed for the changed Python scripts.
- Workflow YAML parsed successfully.
- Build-mode resolver fixture test selected the expected shelf and returned `incremental`.
- `gofmt` completed for `cmd/generate/main.go`.
- `go test ./...` could not run in this environment because the repository requires Go 1.26 and the toolchain download was unavailable (network/DNS blocked). GitHub Actions will run with Go 1.26.

## Important deployment test
After committing the patch:
1. Run `workflow_dispatch` once to force a full build and create `site-state`.
2. Confirm deployment succeeds and branch `site-state` appears.
3. Trigger Refresh for one shelf.
4. Confirm logs say `Build mode: incremental`, only that shelf is scanned, and the other shelves remain intact.
5. Trigger Drive Check and verify it uses the same incremental path for changed shelves.
6. Confirm a lifecycle transition forces a full build.

## Source baseline
Patch was prepared against repository ZIP commit:
`b5290ff586762ca9a07019f4f5a6439433d94a9e`

Review against the current `main` branch before applying if it has advanced since this snapshot.
