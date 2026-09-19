#!/usr/bin/env python3
"""Split generated OPDS feeds into pages of at most 25 book entries."""

from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET

OPDS_ROOT = Path("docs/opds")
PAGE_SIZE = 25
ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/2010/catalog"
ACQ = "http://opds-spec.org/acquisition"
NEXT = "next"
PREVIOUS = "previous"

ET.register_namespace("", ATOM)
ET.register_namespace("opds", OPDS)


def is_book(entry: ET.Element) -> bool:
    return any(
        child.tag == f"{{{ATOM}}}link" and child.get("rel") == ACQ
        for child in entry
    )


def feed_entries(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if child.tag == f"{{{ATOM}}}entry"]


def remove_pagination_links(root: ET.Element) -> None:
    for child in list(root):
        if child.tag == f"{{{ATOM}}}link" and child.get("rel") in {NEXT, PREVIOUS}:
            root.remove(child)


def add_link(root: ET.Element, rel: str, href: str) -> None:
    link = ET.Element(
        f"{{{ATOM}}}link",
        {
            "rel": rel,
            "href": href,
            "type": "application/atom+xml;profile=opds-catalog",
        },
    )
    entries = feed_entries(root)
    if entries:
        root.insert(list(root).index(entries[0]), link)
    else:
        root.append(link)


def page_filename(first_name: str, page: int) -> str:
    if page == 1:
        return first_name
    return f"{Path(first_name).stem}-page-{page}.xml"


def public_page_url(xml_path: Path) -> str:
    rel = xml_path.relative_to(Path("docs")).as_posix()
    return f"https://zenkjt.github.io/tangthu-opds/{rel}"


def is_generated_page(path: Path) -> bool:
    return bool(re.search(r"-page-\d+\.xml$", path.name))


def remove_stale_pages(path: Path) -> None:
    for old in path.parent.glob(f"{path.stem}-page-*.xml"):
        old.unlink()


def paginate_file(path: Path) -> bool:
    tree = ET.parse(path)
    root = tree.getroot()
    entries = feed_entries(root)
    books = [entry for entry in entries if is_book(entry)]

    remove_pagination_links(root)
    remove_stale_pages(path)

    if len(books) <= PAGE_SIZE:
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return False

    folders = [entry for entry in entries if not is_book(entry)]
    chunks = [
        books[i : i + PAGE_SIZE]
        for i in range(0, len(books), PAGE_SIZE)
    ]

    for entry in entries:
        root.remove(entry)

    for entry in folders:
        root.append(entry)
    for entry in chunks[0]:
        root.append(entry)

    page_paths = [
        path.parent / page_filename(path.name, page_no)
        for page_no in range(1, len(chunks) + 1)
    ]

    for page_no, (page_path, chunk) in enumerate(
        zip(page_paths, chunks), start=1
    ):
        if page_no == 1:
            page_root = root
        else:
            page_root = ET.Element(root.tag, root.attrib)
            for child in root:
                if child.tag != f"{{{ATOM}}}entry":
                    page_root.append(
                        ET.fromstring(ET.tostring(child, encoding="unicode"))
                    )
            for entry in chunk:
                page_root.append(
                    ET.fromstring(ET.tostring(entry, encoding="unicode"))
                )

        remove_pagination_links(page_root)

        if page_no > 1:
            add_link(
                page_root,
                PREVIOUS,
                public_page_url(page_paths[page_no - 2]),
            )
        if page_no < len(page_paths):
            add_link(
                page_root,
                NEXT,
                public_page_url(page_paths[page_no]),
            )

        ET.ElementTree(page_root).write(
            page_path,
            encoding="utf-8",
            xml_declaration=True,
        )

    return True


def main() -> None:
    if not OPDS_ROOT.exists():
        raise SystemExit("docs/opds does not exist")

    changed = 0
    paths = [
        p
        for p in sorted(OPDS_ROOT.rglob("*.xml"))
        if not is_generated_page(p)
    ]

    for path in paths:
        if paginate_file(path):
            changed += 1

    print(f"OPDS pagination: {changed} feed(s) split, {PAGE_SIZE} books/page")


if __name__ == "__main__":
    main()
