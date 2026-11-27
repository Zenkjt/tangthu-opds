#!/usr/bin/env python3
"""Choose full or manually requested shelf-scoped generation."""
from __future__ import annotations

import json
import os
from pathlib import Path

EVENT = os.environ.get("GITHUB_EVENT_NAME", "")
EVENT_PATH = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
CATALOG = Path("docs/catalog.json")
CONFIG = Path("config/branches.json")
LIFECYCLE = Path(".build/lifecycle.json")
ACTIVE_CONFIG = Path(".build/branches.json")
OUT = Path(".build")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mode = "full"
    shelves: list[str] = []
    reason = "scheduled or default full build"

    event_data = read_json(EVENT_PATH) if EVENT_PATH.exists() else {}
    inputs = event_data.get("inputs") or {}
    requested_mode = str(inputs.get("build_mode", "full")).strip().lower()

    if EVENT == "workflow_dispatch" and requested_mode == "partial":
        if not all(path.exists() for path in (CATALOG, CONFIG, LIFECYCLE, ACTIVE_CONFIG)):
            reason = "required catalog or lifecycle state missing; full build required"
        else:
            catalog_data = read_json(CATALOG)
            catalog_has_stats = (
                catalog_data.get("version") == 2
                and bool(catalog_data.get("branches"))
                and all(
                    isinstance(row.get("book_count"), int)
                    and isinstance(row.get("font_count"), int)
                    and isinstance(row.get("format_counts"), dict)
                    for row in catalog_data.get("branches", [])
                )
            )

            config_rows = read_json(CONFIG).get("branches", [])
            active_rows = read_json(ACTIVE_CONFIG).get("branches", [])
            catalog_rows = catalog_data.get("branches", [])
            config_ids = {str(row.get("id")) for row in config_rows if row.get("id")}
            active_ids = {str(row.get("id")) for row in active_rows if row.get("id")}
            catalog_ids = {str(row.get("id")) for row in catalog_rows if row.get("id")}

            if not catalog_has_stats:
                reason = "catalog statistics missing or legacy catalog; full build required"
            elif config_ids != catalog_ids:
                reason = "shelf list changed; full build required"
            else:
                catalog_by_id = {str(row.get("id")): row for row in catalog_rows}
                lifecycle_rows = read_json(LIFECYCLE).get("branches", [])
                lifecycle_changed = any(
                    (catalog_by_id.get(str(row.get("id")), {})).get("status", "active")
                    != row.get("status", "active")
                    for row in lifecycle_rows
                )

                def catalog_name(row):
                    value = row.get("name") or row.get("display_name") or ""
                    return value.removeprefix("[SUSPENDED] ")

                names_changed = any(
                    catalog_name(catalog_by_id.get(str(row.get("id")), {})) != row.get("display_name")
                    or catalog_by_id.get(str(row.get("id")), {}).get("root_folder_id") != row.get("root_folder_id")
                    for row in config_rows
                )

                if lifecycle_changed:
                    reason = "shelf lifecycle changed; full build required"
                elif names_changed:
                    reason = "shelf identity or display name changed; full build required"
                else:
                    raw_shelves = str(inputs.get("shelves", "")).strip()
                    requested_ids = (
                        list(dict.fromkeys(item.strip() for item in raw_shelves.split(",") if item.strip()))
                        if raw_shelves
                        else sorted(active_ids)
                    )
                    valid_requested = [item for item in requested_ids if item in active_ids]
                    if valid_requested and len(valid_requested) == len(requested_ids):
                        mode = "incremental"
                        shelves = valid_requested
                        reason = "manual partial build with validated active shelves"
                    else:
                        reason = "empty, inactive, or unknown shelf ID; full build required"

    (OUT / "build_mode").write_text(mode + "\n", encoding="utf-8")
    (OUT / "changed_shelves.txt").write_text(",".join(shelves) + "\n", encoding="utf-8")
    print(f"Build mode: {mode} ({reason})")
    if shelves:
        print("Shelves to update: " + ", ".join(shelves))


if __name__ == "__main__":
    main()
