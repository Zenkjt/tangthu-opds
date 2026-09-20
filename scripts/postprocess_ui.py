#!/usr/bin/env python3
from pathlib import Path

# The catalog generator now owns the complete UI, including the bookshelf view.
# Keep this workflow step for compatibility, but do not apply the old patch:
# that patch expected the previous list-cover HTML/CSS and fails on the new UI.
path = Path("docs/index.html")
if not path.exists():
    raise SystemExit("docs/index.html not found")

text = path.read_text(encoding="utf-8")

required = [
    'class="shelf-view"',
    'function renderShelf()',
    'assets/bookshelf/shelf-row.png',
    'function branchStats(',
]

missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(
        "Generated catalog UI is missing bookshelf elements: " + ", ".join(missing)
    )

print("Catalog UI already contains the current bookshelf implementation; no legacy UI patch needed.")
