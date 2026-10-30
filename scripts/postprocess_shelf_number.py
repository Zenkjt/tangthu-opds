#!/usr/bin/env python3
import json
from pathlib import Path

CONFIG = Path("config/branches.json")
CATALOG = Path("docs/catalog.json")
INDEX = Path("docs/index.html")

MARKER = "/* TANGTHU_SHELF_NO_V1 */"
HELPER = r"""
  /* TANGTHU_SHELF_NO_V1 */
  function shelfLabel(b){
    var name=b && (b.name||b.display_name) || '';
    var no=b && Number(b.shelf_no);
    return no>0 ? name+' #'+no : name;
  }
"""

def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    branches = config.get("branches", [])
    shelf_by_id = {}
    shelf_by_root = {}

    for branch in branches:
        no = branch.get("shelf_no")
        if isinstance(no, bool) or not isinstance(no, int) or no < 1:
            raise SystemExit(
                f"Invalid shelf_no for {branch.get('id') or branch.get('display_name')}: {no!r}"
            )
        if no in shelf_by_id.values():
            raise SystemExit(f"Duplicate shelf_no: {no}")
        shelf_by_id[branch.get("id")] = no
        shelf_by_root[branch.get("root_folder_id")] = no

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_branches = catalog.get("branches", [])
    for branch in catalog_branches:
        no = shelf_by_id.get(branch.get("id"))
        if no is None:
            no = shelf_by_root.get(branch.get("root_folder_id"))
        if no is not None:
            branch["shelf_no"] = no

    CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    text = INDEX.read_text(encoding="utf-8")

    if MARKER not in text:
        anchor = "  function renderBranches(){"
        if anchor not in text:
            raise SystemExit("Shelf-number patch anchor missing: renderBranches")
        text = text.replace(anchor, HELPER + "\n" + anchor, 1)

    text = text.replace(
        "esc(b.name)",
        "esc(shelfLabel(b))",
    )
    text = text.replace(
        "var path=[b.name].concat(folderPath(b,state.parent));",
        "var path=[shelfLabel(b)].concat(folderPath(b,state.parent));",
    )
    text = text.replace(
        "shelf.display_name||shelf.name||''",
        "shelfLabel(shelf)",
    )

    INDEX.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
