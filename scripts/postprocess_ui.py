#!/usr/bin/env python3
from pathlib import Path

# UI is generated completely by cmd/generate/main.go.
# This workflow step remains for pipeline compatibility only.
path = Path("docs/index.html")
if not path.exists():
    raise SystemExit("docs/index.html not found")

print("Apply catalog UI: generated UI is already authoritative; no post-processing required.")
