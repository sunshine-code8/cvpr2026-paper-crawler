from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Paper


@dataclass(frozen=True, slots=True)
class Category:
    name: str
    keywords: tuple[str, ...]
    description: str = ""


def load_categories(path: Path | str) -> list[Category]:
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    values = raw.get("categories", raw) if isinstance(raw, dict) else raw
    if not isinstance(values, list):
        raise ValueError("关键词配置必须是列表，或包含 categories 列表")

    categories: list[Category] = []
    for item in values:
        if not isinstance(item, dict) or not item.get("name") or not item.get("keywords"):
            raise ValueError("每个分类都必须包含 name 和非空 keywords")
        categories.append(
            Category(
                name=str(item["name"]),
                description=str(item.get("description", "")),
                keywords=tuple(str(keyword) for keyword in item["keywords"]),
            )
        )
    return categories


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword.strip())
    # Prevent short ASCII tokens such as "3d", "slam", or "nerf" from
    # accidentally matching inside a longer word.
    if re.fullmatch(r"[\w.+-]+", keyword, flags=re.ASCII):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.I)
    return re.compile(escaped, re.I)


def classify_papers(
    papers: list[Paper],
    categories: list[Category],
    *,
    fallback: str = "其他 / 未分类",
) -> list[Paper]:
    compiled = [
        (category, [(keyword, _keyword_pattern(keyword)) for keyword in category.keywords])
        for category in categories
    ]
    for paper in papers:
        searchable = f"{paper.title}\n{paper.abstract}"
        matches: dict[str, list[str]] = {}
        for category, patterns in compiled:
            hit = [keyword for keyword, pattern in patterns if pattern.search(searchable)]
            if hit:
                matches[category.name] = hit
        paper.matched_keywords = matches
        paper.categories = list(matches) or [fallback]
    return papers

