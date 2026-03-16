"""RSS/Atom 피드에서 기사를 수집하는 모듈."""

import logging
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from collectors.base_collector import Article, BaseCollector
from config.settings import load_sources

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class RSSCollector(BaseCollector):
    """RSS/Atom 피드에서 기사를 수집."""

    def __init__(self):
        sources = load_sources()
        self.feeds: list[dict] = []
        rss_config = sources.get("rss_feeds", {})
        for group in rss_config.values():
            if isinstance(group, list):
                self.feeds.extend(group)
        collection = sources.get("collection", {})
        self.days_back = collection.get("days_back", 7)
        self.delay = collection.get("request_delay", 1.0)
        self.timeout = collection.get("request_timeout", 15)

    def collect(self) -> list[Article]:
        """모든 RSS 피드에서 기사를 수집."""
        articles = []
        cutoff = datetime.now(KST) - timedelta(days=self.days_back)

        for feed_info in self.feeds:
            name = feed_info["name"]
            url = feed_info["url"]
            category = feed_info.get("category", "AI/기술")
            language = feed_info.get("language", "ko")

            try:
                logger.info(f"RSS 수집 중: {name}")
                feed_articles = self._parse_feed(
                    url, name, category, language, cutoff
                )
                articles.extend(feed_articles)
                logger.info(f"  → {len(feed_articles)}건 수집")
            except Exception as e:
                logger.warning(f"  → RSS 수집 실패 ({name}): {e}")

            time.sleep(self.delay)

        return articles

    def _parse_feed(
        self,
        url: str,
        source_name: str,
        category: str,
        language: str,
        cutoff: datetime,
    ) -> list[Article]:
        """단일 RSS 피드를 파싱."""
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            raise ValueError(f"피드 파싱 실패: {feed.bozo_exception}")

        articles = []
        for entry in feed.entries:
            try:
                pub_date = self._parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue

                title = self._clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                if not title or not link:
                    continue

                snippet = self._get_snippet(entry)

                articles.append(
                    Article(
                        title=title,
                        url=link,
                        source_name=source_name,
                        category=category,
                        published_date=pub_date or datetime.now(KST),
                        content_snippet=snippet[:2000],
                        language=language,
                    )
                )
            except Exception as e:
                logger.debug(f"  항목 파싱 스킵: {e}")
                continue

        return articles

    def _parse_date(self, entry) -> datetime | None:
        """피드 항목의 날짜를 파싱."""
        for field in ("published", "updated", "created"):
            raw = entry.get(field)
            if raw:
                try:
                    dt = dateutil_parser.parse(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=KST)
                    return dt
                except (ValueError, TypeError):
                    continue
        return None

    def _get_snippet(self, entry) -> str:
        """피드 항목에서 본문 스니펫 추출."""
        for field in ("summary", "description", "content"):
            raw = entry.get(field)
            if isinstance(raw, list):
                raw = raw[0].get("value", "") if raw else ""
            if raw:
                return self._clean_html(raw)
        return ""

    @staticmethod
    def _clean_html(text: str) -> str:
        """HTML 태그 제거."""
        if "<" in text:
            return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
        return text.strip()
