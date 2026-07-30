from pathlib import Path

from cvpr2026_crawler.classifier import Category
from cvpr2026_crawler.exporters import export_markdown
from cvpr2026_crawler.models import Paper


def test_markdown_is_split_into_browsable_pages(tmp_path: Path) -> None:
    papers = [
        Paper(
            title=f"Paper {index}",
            authors=["Author"],
            paper_url=f"https://example.test/{index}",
            categories=["三维视觉"],
            matched_keywords={"三维视觉": ["3D"]},
        )
        for index in range(5)
    ]
    target = tmp_path / "README.md"
    export_markdown(
        papers,
        [Category("三维视觉", ("3D",), "三维论文。")],
        target,
        page_size=2,
    )

    index = target.read_text(encoding="utf-8")
    pages = sorted((tmp_path / "categories").glob("*.md"))
    assert len(pages) == 3
    assert "1–2" in index
    assert "5–5" in index
    assert "Paper 0" in pages[0].read_text(encoding="utf-8")

