#!/usr/bin/env python3
import json
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

def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    branches = config.get("branches", [])

    shelf_by_id = {}
    shelf_by_root = {}
    used_numbers = set()

    for branch in branches:
        no = branch.get("shelf_no")
        if isinstance(no, bool) or not isinstance(no, int) or no < 1:
            raise SystemExit(
                f"Invalid shelf_no for "
                f"{branch.get('id') or branch.get('display_name')}: {no!r}"
            )
        if no in used_numbers:
            raise SystemExit(f"Duplicate shelf_no: {no}")

        used_numbers.add(no)
        shelf_by_id[branch.get("id")] = no
        shelf_by_root[branch.get("root_folder_id")] = no

    # Inject shelf_no into the generated catalog.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for branch in catalog.get("branches", []):
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

    # The generator/postprocessors may run more than once during local tests.
    # Remove the old V1 helper if present, then install the V2 helper once.
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
    text = text.replace(
        "esc(b.name)",
        "esc(shelfLabel(b))",
    )

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

    # Some bookshelf UI versions assign the display name first and render the
    # variable later. Make that variable itself shelf-number aware.
    text = text.replace(
        "var name=shelf.display_name||shelf.name||'';",
        "var name=shelfLabel(shelf);",
    )
    text = text.replace(
        "var name = shelf.display_name || shelf.name || '';",
        "var name = shelfLabel(shelf);",
    )

    INDEX.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
