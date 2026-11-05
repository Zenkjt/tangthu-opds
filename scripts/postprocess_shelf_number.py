#!/usr/bin/env python3
"""Assign permanent, sequential shelf numbers and render them in the UI/catalog."""
import json
import os
from pathlib import Path

CONFIG = Path("config/branches.json")
CATALOG = Path("docs/catalog.json")
INDEX = Path("docs/index.html")

MARKER = "/* TANGTHU_SHELF_NO_V2 */"
HELPER = r"""
  /* TANGTHU_SHELF_NO_V2 */
  function shelfLabel(b){
    var name=b && (b.name||b.display_name) || '';
    var no=b && Number(b.shelf_no);
    return no>0 ? name+' #'+no : name;
  }
"""


def write_json_atomic(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def assign_missing_numbers(branches):
    """Keep every existing number; append new shelves after the current maximum."""
    used = {}
    for branch in branches:
        no = branch.get("shelf_no")
        if no is None:
            continue
        if isinstance(no, bool) or not isinstance(no, int) or no < 1:
            raise SystemExit(
                f"Invalid shelf_no for {branch.get('id') or branch.get('display_name')}: {no!r}"
            )
        if no in used:
            other = used[no]
            raise SystemExit(
                f"Duplicate shelf_no {no}: {other.get('id') or other.get('display_name')} "
                f"and {branch.get('id') or branch.get('display_name')}"
            )
        used[no] = branch

    next_no = max(used.keys(), default=0) + 1
    assigned = []
    for branch in branches:
        if branch.get("shelf_no") is None:
            branch["shelf_no"] = next_no
            assigned.append((branch.get("display_name") or branch.get("id"), next_no))
            next_no += 1
    return assigned


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    branches = config.get("branches", [])
    if not isinstance(branches, list):
        raise SystemExit("config/branches.json: 'branches' must be an array")

    assigned = assign_missing_numbers(branches)
    if assigned:
        write_json_atomic(CONFIG, config)
        for name, no in assigned:
            print(f"Assigned shelf number #{no}: {name}")
    else:
        print("All shelves already have permanent numbers.")

    shelf_by_id = {}
    shelf_by_root = {}
    for branch in branches:
        no = branch["shelf_no"]
        if branch.get("id"):
            shelf_by_id[branch["id"]] = no
        if branch.get("root_folder_id"):
            shelf_by_root[branch["root_folder_id"]] = no

    # Inject shelf_no into the generated catalog.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for branch in catalog.get("branches", []):
        no = shelf_by_id.get(branch.get("id"))
        if no is None:
            no = shelf_by_root.get(branch.get("root_folder_id"))
        if no is not None:
            branch["shelf_no"] = no

    write_json_atomic(CATALOG, catalog)

    text = INDEX.read_text(encoding="utf-8")

    # Remove the old V1 helper if present, then install V2 exactly once.
    old_marker_start = "  /* TANGTHU_SHELF_NO_V1 */"
    old_helper_start = text.find(old_marker_start)
    if old_helper_start >= 0:
        old_helper_end = text.find("  function renderBranches(){", old_helper_start)
        if old_helper_end >= 0:
            text = text[:old_helper_start] + text[old_helper_end:]

    if MARKER not in text:
        anchor = "  function renderBranches(){"
        if anchor not in text:
            raise SystemExit("Shelf-number patch anchor missing: renderBranches")
        text = text.replace(anchor, HELPER + "\n" + anchor, 1)

    # Main library sidebar.
    text = text.replace("esc(b.name)", "esc(shelfLabel(b))")

    # Current shelf breadcrumb/path.
    text = text.replace(
        "var path=[b.name].concat(folderPath(b,state.parent));",
        "var path=[shelfLabel(b)].concat(folderPath(b,state.parent));",
    )

    # Bookshelf postprocessor variants.
    replacements = [
        ("shelf.display_name||shelf.name||''", "shelfLabel(shelf)"),
        ("shelf.display_name||shelf.name", "shelfLabel(shelf)"),
        ("shelf.display_name || shelf.name || ''", "shelfLabel(shelf)"),
        ("shelf.display_name || shelf.name", "shelfLabel(shelf)"),
        ("(shelf.display_name||shelf.name||'')", "shelfLabel(shelf)"),
        ("(shelf.display_name || shelf.name || '')", "shelfLabel(shelf)"),
    ]
    for old, new_value in replacements:
        text = text.replace(old, new_value)

    text = text.replace(
        "var name=shelf.display_name||shelf.name||'';",
        "var name=shelfLabel(shelf);",
    )
    text = text.replace(
        "var name = shelf.display_name || shelf.name || '';",
        "var name = shelfLabel(shelf);",
    )
    text = text.replace(
        "item.title=shelf.display_name||shelf.name||'';",
        "item.title=shelfLabel(shelf);",
    )
    text = text.replace(
        "item.setAttribute('aria-label',(shelf.display_name||shelf.name||'')+' — '+stats(shelf));",
        "item.setAttribute('aria-label',shelfLabel(shelf)+' — '+stats(shelf));",
    )
    text = text.replace(
        "name.textContent=shelf.display_name||shelf.name||'';",
        "name.textContent=shelfLabel(shelf);",
    )

    INDEX.write_text(text, encoding="utf-8")

    if assigned:
        print(f"Persist {len(assigned)} new shelf number(s) in {CONFIG}.")


if __name__ == "__main__":
    main()
