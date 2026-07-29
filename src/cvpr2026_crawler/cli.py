from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .classifier import classify_papers, load_categories
from .exporters import export_csv, export_json, export_markdown
from .models import Paper
from .scraper import ALL_PAPERS_URL, CVFScraper, ScrapeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="抓取 CVPR 2026 接收论文，并按关键词进行多标签分类。"
    )
    parser.add_argument("--url", default=ALL_PAPERS_URL, help="CVF 全部论文页面")
    parser.add_argument("--keywords", default="config/keywords.yaml", help="关键词 YAML")
    parser.add_argument("--output-dir", default="output", help="输出目录")
    parser.add_argument("--cache-dir", default=".cache/cvpr2026", help="摘要缓存目录")
    parser.add_argument("--workers", type=int, default=6, help="摘要并发请求数")
    parser.add_argument("--timeout", type=float, default=30, help="单次请求超时（秒）")
    parser.add_argument("--retries", type=int, default=4, help="请求重试次数")
    parser.add_argument("--delay", type=float, default=0.15, help="每个摘要请求的礼貌延时")
    parser.add_argument("--limit", type=int, help="仅抓取前 N 篇摘要（调试用）")
    parser.add_argument("--skip-abstracts", action="store_true", help="仅以标题分类")
    parser.add_argument("--refresh", action="store_true", help="忽略已有摘要缓存")
    parser.add_argument(
        "--input-json",
        help="读取已有 papers.json，仅重新分类/导出，不访问网络",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")
    return parser


def _load_json(path: str) -> list[Paper]:
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("输入 JSON 顶层必须是数组")
    return [Paper.from_dict(value) for value in values]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        if args.input_json:
            papers = _load_json(args.input_json)
        else:
            scraper = CVFScraper(
                workers=args.workers,
                timeout=args.timeout,
                retries=args.retries,
                delay=args.delay,
                cache_dir=args.cache_dir,
            )
            papers = scraper.fetch_index(args.url)
            if not args.skip_abstracts:
                papers = scraper.enrich_abstracts(
                    papers, refresh=args.refresh, limit=args.limit
                )

        categories = load_categories(args.keywords)
        classify_papers(papers, categories)
        output_dir = Path(args.output_dir)
        export_json(papers, output_dir / "papers.json")
        export_csv(papers, output_dir / "papers.csv")
        export_markdown(papers, categories, output_dir / "README.md")
        logging.info("完成。结果已写入：%s", output_dir.resolve())
        return 0
    except (OSError, ValueError, ScrapeError, json.JSONDecodeError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

