import os

from .article_pool import ArticlePool
from .config import ROOT, load_settings
from .crawler import article_id, crawl
from .discovery import SourceDiscovery
from .epub import EpubGenerator
from .extractor import ArticleExtractor
from .registry import SourceRegistry
from .validator import validate_epub
from .drive_upload import upload_epub


def run() -> None:
    settings = load_settings()
    registry = SourceRegistry()
    active_sources = [
        source
        for source in registry.list_sources()
        if source.get("status") == "active"
    ]

    output_dir = ROOT / settings.get("storage", {}).get(
        "article_pool", "data/article_pool"
    )
    pool = ArticlePool(output_dir)
    extractor = ArticleExtractor()
    edition_article_ids: set[str] = set()

    for source in active_sources:
        try:
            refs = SourceDiscovery(source, settings).discover()
            print(f"{source['id']}: discovered {len(refs)} article URLs")
        except Exception as exc:
            print(f"{source['id']}: discovery failed: {exc}")
            continue

        try:
            crawl(refs, source, settings, output_dir)
        except Exception as exc:
            print(f"{source['id']}: crawl failed: {exc}")
            continue

        for ref in refs:
            item_id = article_id(ref.url)
            html_path = pool.html_path(ref.source_id, item_id)

            if not html_path.exists():
                print(f"{source['id']}: crawl missing {ref.url}")
                continue

            try:
                article = extractor.extract(html_path, ref.url)
                article["id"] = item_id
                article["source_id"] = ref.source_id
                pool.write_article(article)
                edition_article_ids.add(item_id)
            except Exception as exc:
                print(f"{source['id']}: extraction failed {ref.url}: {exc}")

    epub_path = ROOT / settings.get("storage", {}).get(
        "editions", "data/editions"
    ) / "0neNews.epub"

    EpubGenerator(
        timezone=settings.get("timezone", "Asia/Ho_Chi_Minh")
    ).generate(
        article_pool=output_dir,
        output_path=epub_path,
        sources=active_sources,
        title=settings.get("edition", {}).get("title", "YOUR NEWS"),
        edition_time=settings.get("edition", {}).get("time", "07:00"),
        article_ids=edition_article_ids,
    )
    validate_epub(epub_path)
    print(f"EPUB validated: {epub_path}")

    if os.getenv("TANGTHU_UPLOAD_ENABLED", "false").strip().lower() == "true":
        result = upload_epub(
            epub_path,
            filename=settings.get("drive_upload", {}).get(
                "filename", "0neNews.epub"
            ),
        )
        print(
            "Drive upload complete: "
            f"{result.get('filename', '0neNews.epub')} "
            f"(file_id={result.get('file_id', 'unknown')}, "
            f"operation={result.get('operation', 'unknown')})"
        )
    else:
        print("Drive upload skipped: TANGTHU_UPLOAD_ENABLED is not true.")


if __name__ == "__main__":
    import os
    run()
