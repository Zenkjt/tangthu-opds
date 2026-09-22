#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

CONFIG = Path(os.environ.get("TANGTHU_BRANCH_CONFIG", "config/branches.json"))
BUILD_CONFIG = Path(".build/branches.json")
LIFECYCLE = Path(".build/lifecycle.json")
CATALOG = Path("docs/catalog.json")
API_KEY = os.environ.get("TANGTHU_GOOGLE_API_KEY", "").strip()
FOLDER_MIME = "application/vnd.google-apps.folder"
SUSPEND_DAYS = 7


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso_time(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def check_folder(folder_id):
    params = urllib.parse.urlencode({
        "fields": "id,name,mimeType,trashed",
        "key": API_KEY,
    })
    url = (
        "https://www.googleapis.com/drive/v3/files/"
        + urllib.parse.quote(folder_id, safe="")
        + "?"
        + params
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return "active", json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            return "suspended", {"http_status": 404}
        raise RuntimeError(f"Google Drive API HTTP {exc.code}: {body}")
    except Exception as exc:
        raise RuntimeError(f"Google Drive API error for {folder_id}: {exc}")


def preflight():
    if not API_KEY:
        raise SystemExit("TANGTHU_GOOGLE_API_KEY is required")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = config.get("branches", [])
    active = []
    lifecycle = []
    kept = []
    now = utc_now()
    config_changed = False

    for branch in source:
        row = {
            "id": branch["id"],
            "display_name": branch.get("display_name", ""),
            "root_folder_id": branch["root_folder_id"],
            "status": "disabled" if not branch.get("enabled", True) else "active",
        }

        if not branch.get("enabled", True):
            lifecycle.append(row)
            kept.append(branch)
            continue

        status, info = check_folder(branch["root_folder_id"])

        if status == "active":
            if info.get("mimeType") != FOLDER_MIME or info.get("trashed"):
                status = "suspended"
                info = {"http_status": 200}
            else:
                if "suspended_at" in branch or "suspended_reason" in branch:
                    branch.pop("suspended_at", None)
                    branch.pop("suspended_reason", None)
                    config_changed = True
                branch["enabled"] = True
                branch["last_lifecycle_check"] = iso_time(now)
                row["status"] = "active"
                row["drive_name"] = info.get("name", "")
                active.append(branch)
                lifecycle.append(row)
                kept.append(branch)
                continue

        # Only a confirmed 404 starts/continues the 7-day suspension clock.
        suspended_at = parse_time(branch.get("suspended_at"))
        if suspended_at is None:
            suspended_at = now
            branch["suspended_at"] = iso_time(suspended_at)
            branch["suspended_reason"] = "404"
            config_changed = True

        branch["last_lifecycle_check"] = iso_time(now)
        branch["enabled"] = True
        age = now - suspended_at

        if age >= timedelta(days=SUSPEND_DAYS):
            row["status"] = "removed"
            row["http_status"] = 404
            row["suspended_at"] = branch.get("suspended_at")
            lifecycle.append(row)
            config_changed = True
            # Do not keep removed shelves in branches.json.
            continue

        row["status"] = "suspended"
        row["http_status"] = info.get("http_status")
        row["suspended_at"] = branch.get("suspended_at")
        lifecycle.append(row)
        kept.append(branch)

    if config_changed:
        config["branches"] = kept
        CONFIG.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    BUILD_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    BUILD_CONFIG.write_text(
        json.dumps({"branches": active}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    LIFECYCLE.write_text(
        json.dumps({"branches": lifecycle}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    removed = sum(1 for x in lifecycle if x["status"] == "removed")
    suspended = sum(1 for x in lifecycle if x["status"] == "suspended")
    print(f"Lifecycle preflight: {len(active)} active, {suspended} suspended, {removed} removed.")
    print(f"Lifecycle config changed: {config_changed}")


def merge_suspended():
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = catalog.get("branches") or []
    by_id = {row.get("id"): row for row in rows}

    for life in lifecycle.get("branches", []):
        branch = by_id.get(life["id"])

        if life["status"] == "active":
            if branch is not None:
                branch["status"] = "active"
            continue

        if life["status"] == "disabled":
            if branch is not None:
                branch["status"] = "disabled"
            continue

        if life["status"] == "removed":
            if branch is not None:
                rows.remove(branch)
            continue

        label = life["display_name"]
        if not label.startswith("[SUSPENDED] "):
            label = "[SUSPENDED] " + label

        if branch is None:
            branch = {
                "id": life["id"],
                "display_name": label,
                "root_folder_id": life["root_folder_id"],
                "drive_folder_name": "",
                "status": "suspended",
                "files": [],
            }
            rows.append(branch)
        else:
            branch["display_name"] = label
            branch["status"] = "suspended"
            branch["files"] = []
            branch["drive_folder_name"] = ""

    catalog["branches"] = rows
    CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Lifecycle merge: suspended shelves preserved without stale books; removed shelves deleted.")


if len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "merge"):
    raise SystemExit("Usage: tangthu_lifecycle.py preflight|merge")

if sys.argv[1] == "preflight":
    preflight()
else:
    merge_suspended()
