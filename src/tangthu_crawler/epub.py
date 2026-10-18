from __future__ import annotations

import html
import io
import json
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ebooklib import epub
from PIL import Image, ImageOps


class EpubGenerator:
    def __init__(self, timezone="Asia/Ho_Chi_Minh", image_timeout=15):
        self.timezone = ZoneInfo(timezone)
        self.image_timeout = image_timeout
        self.image_size = (480, 800)

    def _normalize_image(self, source, output_path):
        """Create a CrossPoint-compatible 480x800 grayscale baseline JPEG."""
        image = ImageOps.exif_transpose(source).convert("L")
        image = ImageOps.fit(
            image,
            self.image_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        image.save(
            output_path,
            format="JPEG",
            quality=45,
            progressive=False,
            optimize=True,
            subsampling=2,
        )
        return Path(output_path)

    def generate(
        self,
        article_pool,
        output_path,
        sources,
        title="YOUR NEWS",
        edition_time="07:00",
        article_ids: list[str] | set[str] | None = None,
    ):
        pool = Path(article_pool)
        output = Path(output_path)
        source_map = {s["id"]: s for s in sources}
        allowed_ids = set(article_ids) if article_ids is not None else None
        order_map = (
            {article_id: i for i, article_id in enumerate(article_ids)}
            if isinstance(article_ids, list)
            else {}
        )
        articles = []

        for path in sorted(pool.glob("*/*.json")):
            if path.name.endswith(".meta.json"):
                continue
            article = json.loads(path.read_text(encoding="utf-8"))
            if allowed_ids is not None and article.get("id") not in allowed_ids:
                continue
            source = source_map.get(article.get("source_id"), {})
            if source.get("status", "active") != "active":
                continue
            articles.append(self._apply_policy(article, source.get("policy", {})))

        if order_map:
            articles.sort(key=lambda a: order_map.get(a.get("id"), 10**9))

        source_order = {s.get("id"): i for i, s in enumerate(sources)}
        if source_order:
            articles.sort(
                key=lambda a: (
                    source_order.get(a.get("source_id"), len(source_order)),
                    order_map.get(a.get("id"), 10**9),
                )
            )

        now = datetime.now(self.timezone)
        date_label = now.strftime("%-d %B %Y")

        book = epub.EpubBook()
        book.set_identifier(f"tangthu-news-{now:%Y%m%d}")
        book.set_title(f"{title} at {edition_time} — {date_label}")
        book.set_language("vi")
        book.add_author("Tàng Thư")
        book.add_metadata("DC", "publisher", "Tàng Thư")
        book.add_metadata(
            "DC",
            "description",
            f"{title} at {edition_time} — {date_label}",
        )

        edition = epub.EpubHtml(
            title="Edition",
            file_name="edition.xhtml",
            lang="vi",
        )
        edition.content = self._edition_html(
            title, edition_time, date_label, len(articles)
        )
        book.add_item(edition)

        cover_source = (
            Path(__file__).resolve().parents[2] / "assets" / "0neNews-cover.jpg"
        )
        cover_bytes = (
            cover_source.read_bytes()
            if cover_source.exists()
            else self._make_default_cover(date_label)
        )

        cover_item = epub.EpubItem(
            uid="cover-image",
            file_name="images/cover.jpg",
            media_type="image/jpeg",
            content=cover_bytes,
        )
        cover_item.properties = ["cover-image"]
        book.add_item(cover_item)
        book.add_metadata(
            "OPF",
            "meta",
            "",
            {"name": "cover", "content": "cover-image"},
        )

        cover_page = epub.EpubHtml(
            title="Cover",
            file_name="cover.xhtml",
            lang="vi",
        )
        cover_page.content = """<html xmlns="http://www.w3.org/1999/xhtml" lang="vi"><head><title>YOUR NEWS</title></head><body style="margin:0;padding:0"><img src="images/cover.jpg" alt="Tàng Thư — YOUR NEWS" style="display:block;width:100%;height:auto" /></body></html>"""
        cover_page.add_item(cover_item)
        book.add_item(cover_page)

        article_chapters = []
        image_root = output.parent / ".epub-images"
        if image_root.exists():
            shutil.rmtree(image_root, ignore_errors=True)
        image_root.mkdir(parents=True, exist_ok=True)

        for index, article in enumerate(articles, start=1):
            chapter = epub.EpubHtml(
                title=article["title"] or f"Article {index}",
                file_name=f"article-{index}.xhtml",
                lang="vi",
            )
            image_item = None
            if article.get("image"):
                image_item = self._download_image(
                    article["image"],
                    article.get("url") or article.get("canonical_url"),
                    image_root,
                    index,
                )
                if image_item:
                    book.add_item(image_item)

            chapter.content = self._article_html(article, index, image_item)
            book.add_item(chapter)
            article_chapters.append(chapter)

        # Reader-facing HTML TOC remains hierarchical: Source -> Article.
        toc_page = epub.EpubHtml(
            title="Mục lục",
            file_name="toc.xhtml",
            lang="vi",
        )
        toc_page.content = self._toc_html(articles, source_map)
        book.add_item(toc_page)

        # CrossPoint-compatible native TOC:
        # keep it completely flat so non-touch "Select Chapter" can reach
        # every article directly. Do not put toc.xhtml or nested Sections here.
        book.toc = tuple(
            epub.Link(
                chapter.file_name,
                chapter.title or f"Article {index}",
                chapter.id,
            )
            for index, chapter in enumerate(article_chapters, start=1)
        )

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [cover_page, edition, toc_page, *article_chapters]

        output.parent.mkdir(parents=True, exist_ok=True)
        epub.write_epub(str(output), book)
        shutil.rmtree(image_root, ignore_errors=True)
        return output

    @staticmethod
    def _apply_policy(article, source_policy):
        mode = source_policy.get("mode", "excerpt")
        result = dict(article)
        body = result.get("body") or ""
        if mode == "metadata_only":
            result["body"] = ""
        elif mode == "excerpt":
            result["body"] = body[:800].strip()
        elif mode in {"full_article", "licensed"}:
            result["body"] = body
        else:
            result["body"] = body[:800].strip()
        return result

    @staticmethod
    def _edition_html(title, edition_time, date_label, article_count):
        safe_title = html.escape(title)
        safe_time = html.escape(edition_time)
        safe_date = html.escape(date_label)
        return f"""
<html><head><title>{safe_title}</title></head>
<body>
  <div style="text-align:center; margin-top:28%;">
    <h1 style="font-size:2.2em; margin:0 0 1.2em;">{safe_title}</h1>
    <p style="font-size:1.35em; margin:0 0 0.45em;">{safe_time}</p>
    <p style="font-size:1.25em; margin:0 0 1.8em;">{safe_date}</p>
    <p style="font-size:1.05em; letter-spacing:0.08em;">{article_count} ARTICLES</p>
  </div>
</body></html>
"""

    @staticmethod
    def _toc_html(articles, source_map):
        items = []
        current_source = None

        for index, article in enumerate(articles, start=1):
            source_id = article.get("source_id") or "Nguồn khác"
            source = source_map.get(source_id, {}).get("name") or source_id
            title = html.escape(
                article.get("title") or f"Article {index}"
            )

            if source != current_source:
                if current_source is not None:
                    items.append("</ul>")
                items.append(
                    f"<li><strong>{html.escape(source)}</strong><ul>"
                )
                current_source = source

            items.append(
                f'<li><a href="article-{index}.xhtml">{title}</a></li>'
            )

        if current_source is not None:
            items.append("</ul></li>")

        return (
            """<html><head><title>Mục lục</title></head><body><h1>Mục lục</h1><ul>"""
            + "\n".join(items)
            + """</ul></body></html>"""
        )

    def _download_image(self, url, referer, image_root, index):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Referer": referer or "https://vnexpress.net/",
                },
            )
            with urllib.request.urlopen(req, timeout=self.image_timeout) as response:
                raw = response.read()

            with Image.open(io.BytesIO(raw)) as src:
                path = image_root / f"article-{index}.jpg"
                self._normalize_image(src, path)

            return epub.EpubImage(
                uid=f"image-{index}",
                file_name=f"images/article-{index}.jpg",
                media_type="image/jpeg",
                content=path.read_bytes(),
            )
        except Exception as exc:
            print(f"image download/convert failed {url}: {exc}")
            return None

    @staticmethod
    def _make_default_cover(date_label):
        """Create a valid fallback grayscale baseline JPEG cover (480x800)."""
        image = Image.new("L", (480, 800), 255)
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(image)
        regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        try:
            font = ImageFont.truetype(bold, 50)
            small = ImageFont.truetype(bold, 16)
            detail = ImageFont.truetype(regular, 14)
        except OSError:
            font = small = detail = ImageFont.load_default()

        draw.rectangle((34, 42, 446, 46), fill=0)
        draw.text((34, 75), "TÀNG THƯ / DAILY EDITION", font=small, fill=0)
        draw.text((34, 108), date_label.upper(), font=detail, fill=50)
        draw.line((34, 143, 446, 143), fill=0, width=2)
        draw.text((30, 300), "YOUR", font=font, fill=0)
        draw.text((30, 360), "NEWS", font=font, fill=0)
        draw.rectangle((34, 442, 446, 449), fill=0)
        draw.text((34, 500), "Stories worth", font=small, fill=0)
        draw.text((34, 525), "keeping.", font=small, fill=0)
        draw.line((34, 740, 446, 740), fill=0, width=2)
        draw.text((34, 755), "TÀNG THƯ", font=small, fill=0)

        buffer = io.BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=90,
            progressive=False,
            optimize=False,
            subsampling=0,
        )
        return buffer.getvalue()

    def _article_html(self, article, index, image_item=None):
        title = html.escape(
            article.get("title") or "Untitled",
            quote=False,
        )
        author = html.escape(
            article.get("author") or "",
            quote=False,
        )
        source = html.escape(
            article.get("source_id") or "",
            quote=False,
        )
        published = html.escape(
            article.get("published_at") or "",
            quote=False,
        )
        url = html.escape(
            article.get("canonical_url") or article.get("url") or "",
            quote=False,
        )
        body = article.get("body") or ""

        paragraphs = "\n".join(
            f"<p>{html.escape(line.strip(), quote=False)}</p>"
            for line in body.splitlines()
            if line.strip()
        )
        if not paragraphs and body:
            paragraphs = f"<p>{html.escape(body, quote=False)}</p>"

        meta = " · ".join(
            x for x in (source, published, author) if x
        )
        image_html = (
            f'<p><img src="{html.escape(image_item.file_name)}" alt="" /></p>'
            if image_item
            else ""
        )
        link = (
            f'<p><a href="{url}">Original article</a></p>'
            if url
            else ""
        )

        return (
            f"""<html><head><title>{title}</title></head><body>"""
            f"""<h1>{title}</h1><p>{meta}</p>"""
            f"""{image_html}{paragraphs}{link}</body></html>"""
        )
