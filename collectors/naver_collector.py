"""네이버 뉴스 검색 API로 기사를 수집하는 모듈."""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from dateutil import parser as dateutil_parser

from collectors.base_collector import Article, BaseCollector
from config.settings import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, load_sources

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"


class NaverCollector(BaseCollector):
    """네이버 뉴스 검색 API로 기사를 수집."""

    def __init__(self):
        sources = load_sources()
        naver_config = sources.get("naver_search", {})
        self.queries = naver_config.get("queries", [])
        self.display = naver_config.get("display", 20)
        self.sort = naver_config.get("sort", "date")
        self.days_back = naver_config.get("days_back", 7)
        collection = sources.get("collection", {})
        self.delay = collection.get("request_delay", 1.0)

    def collect(self) -> list[Article]:
        """모든 검색어로 네이버 뉴스를 수집."""
        if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
            logger.warning("네이버 API 키가 설정되지 않았습니다. 네이버 수집을 건너뜁니다.")
            return []

        articles = []
        seen_urls: set[str] = set()
        cutoff = datetime.now(KST) - timedelta(days=self.days_back)

        for query_info in self.queries:
            query = query_info["query"]
            category = query_info.get("category", "채용/HR")

            try:
                logger.info(f"네이버 검색 중: '{query}'")
                results = self._search(query, category, cutoff)

                new_results = []
                for article in results:
                    if article.url not in seen_urls:
                        seen_urls.add(article.url)
                        new_results.append(article)

                articles.extend(new_results)
                logger.info(f"  → {len(new_results)}건 수집")
            except Exception as e:
                logger.warning(f"  → 네이버 검색 실패 ('{query}'): {e}")

            time.sleep(self.delay)

        return articles

    def _search(
        self, query: str, category: str, cutoff: datetime
    ) -> list[Article]:
        """단일 검색어로 네이버 뉴스 API 호출."""
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }
        params = {
            "query": query,
            "display": self.display,
            "start": 1,
            "sort": self.sort,
        }

        response = requests.get(
            NAVER_SEARCH_URL, headers=headers, params=params, timeout=15
        )
        response.raise_for_status()
        data = response.json()

        articles = []
        for item in data.get("items", []):
            try:
                pub_date = dateutil_parser.parse(item.get("pubDate", ""))
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=KST)
                if pub_date < cutoff:
                    continue

                title = self._strip_html(item.get("title", ""))
                url = item.get("originallink") or item.get("link", "")
                description = self._strip_html(item.get("description", ""))

                if not title or not url:
                    continue

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source_name="네이버뉴스",
                        category=category,
                        published_date=pub_date,
                        content_snippet=description[:2000],
                        language="ko",
                    )
                )
            except Exception as e:
                logger.debug(f"  항목 파싱 스킵: {e}")
                continue

        return articles

    @staticmethod
    def _strip_html(text: str) -> str:
        """HTML 태그 및 엔티티 제거."""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        return text.strip()
