from __future__ import annotations

import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import Paper

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://openaccess.thecvf.com"
ALL_PAPERS_URL = f"{BASE_URL}/CVPR2026?day=all"
USER_AGENT = (
    "Mozilla/5.0 (compatible; CVPR2026PaperCrawler/1.0; "
    "+https://github.com/)"
)


class ScrapeError(RuntimeError):
    """Raised when the official CVF page cannot be parsed safely."""


def _clean(text: str) -> str:
    return " ".join(text.split())


def parse_paper_list(html: str, base_url: str = BASE_URL) -> list[Paper]:
    """Parse the CVF ``?day=all`` page.

    CVF represents every paper as a ``dt.ptitle`` followed by one or more
    ``dd`` nodes containing authors and resource links.
    """
    soup = BeautifulSoup(html, "html.parser")
    papers: list[Paper] = []
    seen: set[str] = set()

    for title_node in soup.select("dt.ptitle"):
        title_link = title_node.find("a", href=True)
        if not title_link:
            continue
        paper_url = urljoin(base_url, title_link["href"])
        if paper_url in seen:
            continue

        authors: list[str] = []
        pdf_url = ""
        supplemental_url = ""
        sibling = title_node.find_next_sibling()
        while sibling and sibling.name == "dd":
            classes = set(sibling.get("class", []))
            is_author_node = (
                "authors" in classes
                or sibling.select_one("form.authsearch, input[name='query_author']")
                is not None
            )
            if is_author_node:
                authors = [_clean(a.get_text(" ", strip=True)) for a in sibling.find_all("a")]
                if not authors:
                    authors = [
                        _clean(node.get("value", ""))
                        for node in sibling.select("input[name='query_author']")
                        if _clean(node.get("value", ""))
                    ]
                if not authors:
                    authors = [
                        value.strip()
                        for value in _clean(sibling.get_text(" ", strip=True)).split(",")
                        if value.strip()
                    ]
            for link in sibling.find_all("a", href=True):
                label = _clean(link.get_text(" ", strip=True)).lower()
                href = urljoin(base_url, link["href"])
                if label == "pdf" or href.lower().endswith(".pdf") and "supplemental" not in href:
                    pdf_url = href
                elif "supp" in label or "supplemental" in href:
                    supplemental_url = href
            sibling = sibling.find_next_sibling()

        papers.append(
            Paper(
                title=_clean(title_link.get_text(" ", strip=True)),
                authors=authors,
                paper_url=paper_url,
                pdf_url=pdf_url,
                supplemental_url=supplemental_url,
            )
        )
        seen.add(paper_url)

    if not papers:
        raise ScrapeError(
            "没有从页面中解析到论文。CVF 页面结构可能已变化，"
            "或服务器返回了验证/限流页面。"
        )
    return papers


def parse_abstract(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("#abstract")
    if node:
        return _clean(node.get_text(" ", strip=True))
    # Defensive fallback for small markup changes.
    heading = soup.find(
        lambda tag: tag.name in {"h2", "h3", "div"}
        and _clean(tag.get_text(" ", strip=True)).lower() == "abstract"
    )
    if heading:
        sibling = heading.find_next_sibling()
        if sibling:
            return _clean(sibling.get_text(" ", strip=True))
    return ""


class CVFScraper:
    def __init__(
        self,
        *,
        workers: int = 6,
        timeout: float = 30.0,
        retries: int = 4,
        delay: float = 0.15,
        cache_dir: Path | str = ".cache/cvpr2026",
    ) -> None:
        self.workers = max(1, workers)
        self.timeout = timeout
        self.retries = max(1, retries)
        self.delay = max(0.0, delay)
        self.cache_dir = Path(cache_dir)
        self.abstract_dir = self.cache_dir / "abstracts"
        self._write_lock = Lock()

    def _get_text(self, url: str) -> str:
        last_error: Exception | None = None
        # CVF serves its conference route through Apache content negotiation.
        # An HTML-only Accept header can produce 406 because the route resolves
        # internally to proceedings.py, so retain the browser-compatible */*.
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
        for attempt in range(self.retries):
            try:
                with httpx.Client(
                    headers=headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    return response.text
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    wait = (2**attempt) + random.uniform(0, 0.5)
                    LOGGER.warning("请求失败，%.1f 秒后重试：%s", wait, url)
                    time.sleep(wait)
        raise ScrapeError(f"请求失败（已重试 {self.retries} 次）：{url}") from last_error

    def fetch_index(self, url: str = ALL_PAPERS_URL) -> list[Paper]:
        LOGGER.info("正在抓取论文索引：%s", url)
        papers = parse_paper_list(self._get_text(url))
        LOGGER.info("索引中共解析到 %d 篇论文", len(papers))
        return papers

    @staticmethod
    def _cache_key(paper: Paper) -> str:
        stem = Path(paper.paper_url).stem
        return "".join(ch for ch in stem if ch.isalnum() or ch in "-_")[:180]

    def _fetch_one_abstract(self, paper: Paper, refresh: bool) -> Paper:
        cache_path = self.abstract_dir / f"{self._cache_key(paper)}.json"
        if cache_path.exists() and not refresh:
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                paper.abstract = cached.get("abstract", "")
                return paper
            except (OSError, json.JSONDecodeError):
                LOGGER.warning("忽略损坏的缓存：%s", cache_path)

        if self.delay:
            time.sleep(self.delay + random.uniform(0, self.delay / 2))
        paper.abstract = parse_abstract(self._get_text(paper.paper_url))
        self.abstract_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"paper_url": paper.paper_url, "abstract": paper.abstract},
            ensure_ascii=False,
            indent=2,
        )
        with self._write_lock:
            cache_path.write_text(payload + "\n", encoding="utf-8")
        return paper

    def enrich_abstracts(
        self,
        papers: list[Paper],
        *,
        refresh: bool = False,
        limit: int | None = None,
    ) -> list[Paper]:
        selected = papers[:limit] if limit is not None else papers
        if not selected:
            return papers

        LOGGER.info(
            "正在获取 %d 篇论文摘要（并发=%d，支持断点缓存）",
            len(selected),
            self.workers,
        )
        failures: list[tuple[str, Exception]] = []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self._fetch_one_abstract, paper, refresh): paper
                for paper in selected
            }
            for completed, future in enumerate(as_completed(futures), start=1):
                paper = futures[future]
                try:
                    future.result()
                except Exception as exc:  # Keep the complete run resumable.
                    failures.append((paper.title, exc))
                    LOGGER.error("摘要抓取失败：%s (%s)", paper.title, exc)
                if completed % 100 == 0 or completed == len(selected):
                    LOGGER.info("摘要进度：%d/%d", completed, len(selected))

        if failures:
            LOGGER.warning(
                "%d 篇摘要暂时失败；再次运行会利用缓存并重试失败项", len(failures)
            )
        return papers
