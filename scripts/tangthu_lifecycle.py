#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path(os.environ.get("TANGTHU_BRANCH_CONFIG", "config/branches.json"))
BUILD_CONFIG = Path(".build/branches.json")
LIFECYCLE = Path("docs/lifecycle.json")
CATALOG = Path("docs/catalog.json")
INDEX = Path("docs/index.html")
API_KEY = os.environ.get("TANGTHU_GOOGLE_API_KEY", "").strip()

FOLDER_MIME = "application/vnd.google-apps.folder"


def drive_folder(folder_id):
    params = urllib.parse.urlencode({
        "fields": "id,name,mimeType,trashed",
        "key": API_KEY,
    })
    url = (
        "https://www.googleapis.com/drive/v3/files/"
        f"{urllib.parse.quote(folder_id, safe='')}?{params}"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return "active", json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        reasons = {
            str(item.get("reason", "")).lower()
            for item in (payload.get("error", {}).get("errors", []) or [])
            if isinstance(item, dict)
        }

        # Chỉ coi 404 hoặc 403 do quyền truy cập là suspended.
        # Quota / invalid key / rate limit vẫn phải làm build fail.
        if exc.code == 404 or (
            exc.code == 403
            and reasons.intersection({
                "forbidden",
                "insufficientfilepermissions",
                "notfound",
            })
        ):
            return "suspended", {
                "http_status": exc.code,
                "reasons": sorted(reasons),
            }

        raise RuntimeError(
            f"Google Drive API HTTP {exc.code}: {body}"
        )
    except Exception as exc:
        raise RuntimeError(
            f"Google Drive API error for {folder_id}: {exc}"
        )


def preflight():
    if not API_KEY:
        raise SystemExit("TANGTHU_GOOGLE_API_KEY is required")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    branches = config.get("branches") or []
    active = []
    lifecycle = []

    for branch in branches:
        if not branch.get("enabled", True):
            lifecycle.append({
                "id": branch["id"],
                "name": branch.get("display_name", ""),
                "root_folder_id": branch["root_folder_id"],
                "status": "disabled",
            })
            continue

        status, info = drive_folder(branch["root_folder_id"])
        row = {
            "id": branch["id"],
            "name": branch.get("display_name", ""),
            "root_folder_id": branch["root_folder_id"],
            "status": status,
        }

        if status == "active":
            if info.get("mimeType") != FOLDER_MIME or info.get("trashed"):
                row["status"] = "suspended"
            else:
                active.append(branch)
                row["drive_name"] = info.get("name", "")

        if status == "suspended":
            row["http_status"] = info.get("http_status")

        lifecycle.append(row)

    BUILD_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    BUILD_CONFIG.write_text(
        json.dumps({"branches": active}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    LIFECYCLE.parent.mkdir(parents=True, exist_ok=True)
    LIFECYCLE.write_text(
        json.dumps({"branches": lifecycle}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    suspended = sum(
        1 for item in lifecycle if item["status"] == "suspended"
    )
    print(
        f"Lifecycle preflight: {len(active)} active, "
        f"{suspended} suspended."
    )


def finalize():
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    statuses = {item["id"]: item for item in lifecycle.get("branches", [])}

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = catalog.get("branches") or []
    seen = {item.get("id") for item in rows}

    for branch in rows:
        life = statuses.get(branch.get("id"))
        branch["status"] = life["status"] if life else "active"

    # Generator chỉ nhìn thấy active shelves.
    # Ở đây thêm lại suspended shelf với files=[] để sách cũ biến mất khỏi catalog.
    for life in lifecycle.get("branches", []):
        if life["status"] != "suspended" or life["id"] in seen:
            continue

        rows.append({
            "id": life["id"],
            "name": life["name"],
            "root_folder_id": life["root_folder_id"],
            "drive_name": "",
            "status": "suspended",
            "files": [],
        })

    catalog["branches"] = rows
    CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # postprocess_bookshelf.py đã tạo bookshelf view cuối cùng.
    # Patch lifecycle status vào đúng chỗ thống kê sách.
    text = INDEX.read_text(encoding="utf-8")

    old_stats = """    function statsLines(shelf){
      var files=shelfFiles(shelf), counts={};
      files.forEach(function(f){var e=extension(f.name);if(e)counts[e]=(counts[e]||0)+1;});
      return [
        files.length+' sách',
        'EPUB '+(counts.EPUB||0),
        'MOBI '+(counts.MOBI||0),
        'AZW3 '+(counts.AZW3||0)
      ];
    }"""

    new_stats = """    function statsLines(shelf){
      var files=shelfFiles(shelf), counts={};
      files.forEach(function(f){var e=extension(f.name);if(e)counts[e]=(counts[e]||0)+1;});
      if(shelf.status==='suspended'){
        return ['SUSPENDED · Tủ tạm ngưng', 'Không thể truy cập Google Drive'];
      }
      return [
        files.length+' sách',
        'EPUB '+(counts.EPUB||0),
        'MOBI '+(counts.MOBI||0),
        'AZW3 '+(counts.AZW3||0)
      ];
    }"""

    if old_stats not in text:
        raise SystemExit("Lifecycle UI anchor missing: statsLines")
    text = text.replace(old_stats, new_stats, 1)

    old_name = """        name.textContent=shelf.display_name||shelf.name||'';"""
    new_name = """        name.textContent=(shelf.display_name||shelf.name||'')+
          (shelf.status==='suspended'?' [SUSPENDED]':'');"""

    if old_name not in text:
        raise SystemExit("Lifecycle UI anchor missing: shelf name")
    text = text.replace(old_name, new_name, 1)

    old_click = """        item.onclick=(function(s){return function(){openShelf(s);};})(shelf);"""
    new_click = """        item.onclick=(function(s){return function(){
          if(s.status==='suspended') return;
          openShelf(s);
        };})(shelf);"""

    if old_click not in text:
        raise SystemExit("Lifecycle UI anchor missing: shelf click")
    text = text.replace(old_click, new_click, 1)

    INDEX.write_text(text, encoding="utf-8")
    print("Lifecycle finalize: catalog and bookshelf UI updated.")


if len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "finalize"):
    raise SystemExit("Usage: lifecycle.py preflight|finalize")

if sys.argv[1] == "preflight":
    preflight()
else:
    finalize()
