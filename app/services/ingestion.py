import logging
from datetime import UTC, datetime

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.db import Article, Source

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def detect_source_type(self, url: str) -> str:
        lowered = url.lower()
        if any(token in lowered for token in ("feed", "rss", "atom", ".xml")):
            return "rss"
        return "web"

    def ingest_all_sources(self) -> int:
        count = 0
        for source in self.db.query(Source).filter(Source.active.is_(True)).all():
            try:
                count += self.ingest_source(source)
            except Exception:
                logger.exception("Failed to ingest source %s (%s)", source.name, source.url)
        return count

    def ingest_source(self, source: Source) -> int:
        if source.source_type == "web":
            return self._ingest_web_page(source)
        return self._ingest_feed(source)

    def _ingest_feed(self, source: Source) -> int:
        parsed = feedparser.parse(source.url)
        if parsed.bozo and not parsed.entries:
            logger.warning("Feed parse error for %s: %s", source.url, parsed.bozo_exception)
            return 0
        added = 0
        for entry in parsed.entries[:30]:
            url = entry.get("link")
            if not url or self.db.query(Article).filter(Article.url == url).first():
                continue
            content = ""
            if entry.get("summary"):
                content = BeautifulSoup(entry["summary"], "html.parser").get_text(" ", strip=True)
            elif entry.get("content"):
                content = BeautifulSoup(entry["content"][0].get("value", ""), "html.parser").get_text(" ", strip=True)
            article = Article(
                source_id=source.id,
                title=entry.get("title", "Untitled"),
                author=entry.get("author"),
                url=url,
                published_at=self._parse_date(entry),
                content=content[:15000],
            )
            self.db.add(article)
            added += 1
        self.db.commit()
        return added

    def _ingest_web_page(self, source: Source) -> int:
        try:
            response = httpx.get(source.url, timeout=15)
            response.raise_for_status()
        except Exception:
            logger.exception("Failed to fetch web page %s", source.url)
            return 0
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else source.name
        text = soup.get_text(" ", strip=True)[:15000]
        if self.db.query(Article).filter(Article.url == source.url).first():
            return 0
        article = Article(source_id=source.id, title=title, author=None, url=source.url, published_at=datetime.now(UTC), content=text)
        self.db.add(article)
        self.db.commit()
        return 1

    @staticmethod
    def _parse_date(entry: dict) -> datetime | None:
        if entry.get("published_parsed"):
            return datetime(*entry.published_parsed[:6])
        return None
