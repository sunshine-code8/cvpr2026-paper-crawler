from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .classifier import Category
from .models import Paper


def export_json(papers: list[Paper], path: Path | str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([paper.to_dict() for paper in papers], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def export_csv(papers: list[Paper], path: Path | str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "title",
                "authors",
                "abstract",
                "categories",
                "matched_keywords",
                "paper_url",
                "pdf_url",
                "supplemental_url",
            ],
        )
        writer.writeheader()
        for paper in papers:
            writer.writerow(
                {
                    "title": paper.title,
                    "authors": "; ".join(paper.authors),
                    "abstract": paper.abstract,
                    "categories": "; ".join(paper.categories),
                    "matched_keywords": json.dumps(
                        paper.matched_keywords, ensure_ascii=False
                    ),
                    "paper_url": paper.paper_url,
                    "pdf_url": paper.pdf_url,
                    "supplemental_url": paper.supplemental_url,
                }
            )


def export_markdown(
    papers: list[Paper],
    categories: list[Category],
    path: Path | str,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[Paper]] = defaultdict(list)
    for paper in papers:
        for category in paper.categories:
            grouped[category].append(paper)

    ordered_names = [category.name for category in categories]
    for name in grouped:
        if name not in ordered_names:
            ordered_names.append(name)
    counts = Counter(category for paper in papers for category in paper.categories)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# CVPR 2026 接收论文关键词分类",
        "",
        f"- 论文总数：**{len(papers)}**",
        f"- 分类方式：标题 + 摘要关键词，多标签归类",
        f"- 生成时间：{now}",
        f"- 官方来源：[CVF OpenAccess](https://openaccess.thecvf.com/CVPR2026?day=all)",
        "",
        "## 分类统计",
        "",
        "| 分类 | 论文数 |",
        "|---|---:|",
    ]
    for name in ordered_names:
        if counts[name]:
            lines.append(f"| {name} | {counts[name]} |")

    lines.extend(["", "> 同一篇论文可能属于多个分类，因此分类数之和可能大于论文总数。", ""])
    descriptions = {category.name: category.description for category in categories}
    for name in ordered_names:
        category_papers = sorted(grouped.get(name, []), key=lambda item: item.title.lower())
        if not category_papers:
            continue
        lines.extend([f"## {name} ({len(category_papers)})", ""])
        if descriptions.get(name):
            lines.extend([descriptions[name], ""])
        for paper in category_papers:
            title = paper.title.replace("[", r"\[").replace("]", r"\]")
            links = [f"[主页]({paper.paper_url})"]
            if paper.pdf_url:
                links.append(f"[PDF]({paper.pdf_url})")
            matched = ", ".join(paper.matched_keywords.get(name, []))
            suffix = f" — 命中：`{matched}`" if matched else ""
            lines.append(f"- **[{title}]({paper.paper_url})** ({' / '.join(links)}){suffix}")
            if paper.authors:
                lines.append(f"  - 作者：{', '.join(paper.authors)}")
        lines.append("")

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

