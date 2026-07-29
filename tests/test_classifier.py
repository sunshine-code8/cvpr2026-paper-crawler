from cvpr2026_crawler.classifier import Category, classify_papers
from cvpr2026_crawler.models import Paper


def test_multilabel_classification_uses_title_and_abstract() -> None:
    paper = Paper(
        title="A Vision-Language Model",
        authors=[],
        paper_url="https://example.test/paper",
        abstract="We reconstruct a 3D scene with a robot.",
    )
    categories = [
        Category("多模态", ("vision-language", "multimodal")),
        Category("三维", ("3D", "point cloud")),
        Category("机器人", ("robot",)),
    ]
    classify_papers([paper], categories)
    assert paper.categories == ["多模态", "三维", "机器人"]
    assert paper.matched_keywords["多模态"] == ["vision-language"]


def test_ascii_keyword_does_not_match_inside_word() -> None:
    paper = Paper("Target tracking", [], "https://example.test")
    classify_papers([paper], [Category("三维", ("3D",))])
    assert paper.categories == ["其他 / 未分类"]

