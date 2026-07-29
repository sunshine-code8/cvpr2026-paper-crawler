from pathlib import Path

import pytest

from cvpr2026_crawler.scraper import ScrapeError, parse_abstract, parse_paper_list


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_paper_list() -> None:
    papers = parse_paper_list((FIXTURES / "index.html").read_text(encoding="utf-8"))
    assert len(papers) == 2
    assert papers[0].title == "A Vision-Language Model for 3D Robotics"
    assert papers[0].authors == ["Wei Li", "Ada Chen"]
    assert papers[0].paper_url.startswith("https://openaccess.thecvf.com/content/")
    assert papers[0].pdf_url.endswith("_paper.pdf")
    assert papers[0].supplemental_url.endswith("_supplemental.pdf")


def test_parse_abstract() -> None:
    html = (FIXTURES / "paper.html").read_text(encoding="utf-8")
    assert parse_abstract(html) == (
        "We introduce a multimodal robot that reconstructs a 3D scene."
    )


def test_empty_index_is_rejected() -> None:
    with pytest.raises(ScrapeError):
        parse_paper_list("<html><body>rate limited</body></html>")

