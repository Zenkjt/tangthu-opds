#!/usr/bin/env python3
"""Choose full or shelf-scoped generation for the shared OPDS workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path

EVENT = os.environ.get("GITHUB_EVENT_NAME", "")
EVENT_PATH = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
CATALOG = Path("docs/catalog.json")
CONFIG = Path("config/branches.json")
LIFECYCLE = Path(".build/lifecycle.json")
OUT = Path(".build")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mode = "full"
    shelves: list[str] = []
    reason = "manual, scheduled, or no reusable site-state"

    if EVENT == "repository_dispatch" and CATALOG.exists() and LIFECYCLE.exists():
        payload = read_json(EVENT_PATH) if EVENT_PATH.exists() else {}
        requested = payload.get("client_payload", {}).get("shelves", [])
        config_rows = read_json(CONFIG).get("branches", [])
        config_ids = {str(row.get("id")) for row in config_rows if row.get("id")}
        active_rows = read_json(Path(".build/branches.json")).get("branches", [])
        active_ids = {str(row.get("id")) for row in active_rows if row.get("id")}
        catalog_rows = read_json(CATALOG).get("branches", [])
        catalog_ids = {str(row.get("id")) for row in catalog_rows if row.get("id")}

        if config_ids != catalog_ids:
            reason = "shelf list changed; full build required"
        else:
            catalog_by_id = {str(row.get("id")): row for row in catalog_rows}
            lifecycle_rows = read_json(LIFECYCLE).get("branches", [])
            lifecycle_changed = False
            for row in lifecycle_rows:
                shelf_id = str(row.get("id", ""))
                current = catalog_by_id.get(shelf_id)
                old_status = (current or {}).get("status", "active")
                new_status = row.get("status", "active")
                if old_status != new_status:
                    lifecycle_changed = True
                    break
            def catalog_name(row):
                value = row.get("name") or row.get("display_name") or ""
                return value.removeprefix("[SUSPENDED] ")

            names_changed = any(
                (catalog_name(catalog_by_id.get(str(row.get("id")), {})) != row.get("display_name"))
                or (catalog_by_id.get(str(row.get("id")), {}).get("root_folder_id") != row.get("root_folder_id"))
                for row in config_rows
            )
            if lifecycle_changed:
                reason = "shelf lifecycle changed; full build required"
            elif names_changed:
                reason = "shelf identity or display name changed; full build required"
            else:
                requested_ids = list(dict.fromkeys(str(item) for item in requested))
                valid_requested = [item for item in requested_ids if item in active_ids]
                if valid_requested and len(valid_requested) == len(requested_ids):
                    mode = "incremental"
                    shelves = valid_requested
                    reason = "repository_dispatch with unchanged lifecycle"
                else:
                    reason = "empty, inactive, or unknown shelf list; full build required"

    (OUT / "build_mode").write_text(mode + "\n", encoding="utf-8")
    (OUT / "changed_shelves.txt").write_text(",".join(shelves) + "\n", encoding="utf-8")
    print(f"Build mode: {mode} ({reason})")
    if shelves:
        print("Shelves to update: " + ", ".join(shelves))


if __name__ == "__main__":
    main()
