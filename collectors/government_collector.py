"""정부 보도자료를 수집하는 모듈. RSS 기반."""

import logging

from collectors.base_collector import Article, BaseCollector
from collectors.rss_collector import RSSCollector
from config.settings import load_sources

logger = logging.getLogger(__name__)


class GovernmentCollector(BaseCollector):
    """정부 부처 RSS 피드에서 보도자료를 수집.

    정부 소스는 sources.yaml의 rss_feeds.government에 정의되어 있으며,
    RSSCollector와 동일한 메커니즘으로 수집합니다.
    별도 클래스로 분리한 이유는 향후 스크래핑 로직 추가 가능성 때문.
    """

    def __init__(self):
        sources = load_sources()
        self.feeds = sources.get("rss_feeds", {}).get("government", [])
        collection = sources.get("collection", {})
        self.days_back = collection.get("days_back", 7)
        self.delay = collection.get("request_delay", 1.0)

    def collect(self) -> list[Article]:
        """정부 RSS 피드에서 보도자료를 수집."""
        if not self.feeds:
            logger.info("정부 소스가 설정되지 않았습니다.")
            return []

        # RSSCollector의 피드 파싱 로직을 재사용
        rss = RSSCollector()
        # 정부 피드만 사용하도록 교체
        rss.feeds = self.feeds
        articles = rss.collect()

        logger.info(f"정부 보도자료 총 {len(articles)}건 수집")
        return articles
