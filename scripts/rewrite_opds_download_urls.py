#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

OPDS_ROOT = Path("docs/opds")
ATOM = "http://www.w3.org/2005/Atom"
ACQ = "http://opds-spec.org/acquisition"


def worker_base_url() -> str:
    value = os.environ.get("TANGTHU_DOWNLOAD_WORKER_URL", "").strip().rstrip("/")
    if not value:
        raise SystemExit("TANGTHU_DOWNLOAD_WORKER_URL is required")
    return value


def rewrite_file(path: Path, base_url: str) -> int:
    tree = ET.parse(path)
    root = tree.getroot()
    changed = 0

    for entry in root.findall(f"{{{ATOM}}}entry"):
        for link in entry.findall(f"{{{ATOM}}}link"):
            if link.get("rel") != ACQ:
                continue

            href = link.get("href", "")
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            file_id = query.get("id", [""])[0]

            if not file_id:
                continue

            new_href = f"{base_url}/download/{file_id}"

            if href != new_href:
                link.set("href", new_href)
                changed += 1

    if changed:
        tree.write(path, encoding="utf-8", xml_declaration=True)

    return changed


def main() -> None:
    if not OPDS_ROOT.exists():
        raise SystemExit("docs/opds does not exist")

    base_url = worker_base_url()

    files = sorted(OPDS_ROOT.rglob("*.xml"))
    changed = sum(rewrite_file(path, base_url) for path in files)

    print(
        f"OPDS download URLs: rewritten {changed} "
        f"acquisition link(s) using {base_url}"
    )


if __name__ == "__main__":
    main()
