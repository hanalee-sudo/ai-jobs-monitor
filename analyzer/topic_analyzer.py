"""토픽 클러스터링 및 종합 분석 모듈."""

import json
import logging
import re
import time

import anthropic

from analyzer.topic_prompts import (
    CLUSTERING_SYSTEM_PROMPT,
    CLUSTERING_USER_TEMPLATE,
    KEYWORD_SUGGESTION_SYSTEM_PROMPT,
    KEYWORD_SUGGESTION_USER_TEMPLATE,
    TOPIC_ANALYSIS_SYSTEM_PROMPT,
    TOPIC_ANALYSIS_USER_TEMPLATE,
)
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_TOPIC = 40
SNIPPET_TRUNCATE = 1000  # 기사가 많을 때 snippet 축소


class TopicAnalyzer:
    """2단계 Claude 분석: 클러스터링 → 토픽별 심층 분석."""

    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def generate_report(self, articles: list[dict], days: int = 7) -> dict:
        """기사 목록에서 5개 토픽 리포트를 생성."""
        logger.info(f"토픽 리포트 생성 시작 ({len(articles)}개 기사, {days}일)")

        # Phase 1: 클러스터링
        logger.info("[Phase 1] 기사 클러스터링...")
        clusters = self._cluster_articles(articles, days)
        logger.info(f"  → {len(clusters)}개 토픽 생성")

        # Phase 2: 토픽별 심층 분석
        logger.info("[Phase 2] 토픽별 심층 분석...")
        topics = []
        for i, cluster in enumerate(clusters, 1):
            logger.info(f"  분석 중 ({i}/{len(clusters)}): {cluster['topic_name']}")
            topic = self._analyze_topic(cluster, articles)
            topics.append(topic)
            if i < len(clusters):
                time.sleep(5)

        # 기간 계산
        dates = [a.get("collected_date", "") for a in articles if a.get("collected_date")]
        period_start = min(dates) if dates else ""
        period_end = max(dates) if dates else ""

        return {
            "period_start": period_start,
            "period_end": period_end,
            "article_count": len(articles),
            "topics": topics,
        }

    def _cluster_articles(self, articles: list[dict], days: int) -> list[dict]:
        """Phase 1: 기사 목록을 5개 토픽으로 클러스터링."""
        # 컴팩트 기사 목록 구성
        article_lines = []
        for a in articles:
            snippet = (a.get("content_snippet") or "")[:150]
            line = f"[ID:{a['id']}] {a['title']} ({a['source_name']}) - {snippet}"
            article_lines.append(line)

        article_list = "\n".join(article_lines)
        user_prompt = CLUSTERING_USER_TEMPLATE.format(
            days=days, count=len(articles), article_list=article_list
        )

        response = self._call_api(
            CLUSTERING_SYSTEM_PROMPT, user_prompt, max_tokens=2048
        )

        # JSON 파싱
        clusters = self._parse_json(response)
        if not clusters or "topics" not in clusters:
            logger.error("클러스터링 JSON 파싱 실패. 기본 클러스터 생성.")
            return self._fallback_clusters(articles)

        # article_ids 검증
        valid_ids = {a["id"] for a in articles}
        for topic in clusters["topics"]:
            topic["article_ids"] = [
                aid for aid in topic.get("article_ids", []) if aid in valid_ids
            ]

        return clusters["topics"][:10]

    def _analyze_topic(self, cluster: dict, all_articles: list[dict]) -> dict:
        """Phase 2: 단일 토픽의 기사들을 종합 분석."""
        article_ids = set(cluster.get("article_ids", []))
        topic_articles = [a for a in all_articles if a["id"] in article_ids]

        # 기사가 너무 많으면 snippet 축소
        snippet_len = 2000
        if len(topic_articles) > MAX_ARTICLES_PER_TOPIC:
            topic_articles = topic_articles[:MAX_ARTICLES_PER_TOPIC]
            snippet_len = SNIPPET_TRUNCATE

        # 기사 상세 구성
        detail_parts = []
        for a in topic_articles:
            snippet = (a.get("content_snippet") or "")[:snippet_len]
            url = a.get('url', '')
            part = f"### {a['title']}\n출처: {a['source_name']} | 날짜: {a.get('published_date', '')[:10]} | URL: {url}\n{snippet}\n"
            detail_parts.append(part)

        articles_detail = "\n---\n".join(detail_parts)
        user_prompt = TOPIC_ANALYSIS_USER_TEMPLATE.format(
            topic_name=cluster["topic_name"],
            count=len(topic_articles),
            articles_detail=articles_detail,
        )

        response = self._call_api(
            TOPIC_ANALYSIS_SYSTEM_PROMPT, user_prompt, max_tokens=4096
        )

        # 섹션 추출
        return {
            "rank": cluster.get("rank", 0),
            "topic_name": cluster["topic_name"],
            "topic_summary": self._extract_section(response, "종합 요약"),
            "key_insights": self._extract_section(response, "핵심 인사이트"),
            "business_angle": self._extract_section(response, "비즈니스 앵글"),
            "article_ids": cluster.get("article_ids", []),
        }

    def suggest_keywords(self, articles: list[dict], current_keywords: list[str]) -> dict:
        """수집된 기사를 분석하여 키워드 추가/삭제를 추천."""
        titles = [a["title"] for a in articles]
        title_list = "\n".join(f"- {t}" for t in titles[:300])
        keyword_list = "\n".join(f"- {k}" for k in current_keywords)

        user_prompt = KEYWORD_SUGGESTION_USER_TEMPLATE.format(
            current_keywords=keyword_list,
            article_titles=title_list,
        )

        response = self._call_api(
            KEYWORD_SUGGESTION_SYSTEM_PROMPT, user_prompt, max_tokens=2048
        )

        result = self._parse_json(response)
        if not result:
            return {"add": [], "remove": [], "summary": "키워드 분석 실패"}
        return result

    def _call_api(self, system_prompt: str, user_prompt: str,
                  max_tokens: int = 4096, retries: int = 5) -> str:
        """Claude API 호출 (재시도 포함)."""
        for attempt in range(retries):
            try:
                message = self.client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return message.content[0].text
            except anthropic.RateLimitError:
                wait = 10 * (attempt + 1)
                logger.warning(f"Rate limit 도달. {wait}초 대기 후 재시도...")
                time.sleep(wait)
            except Exception as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"API 호출 실패 (시도 {attempt + 1}): {e}")
                time.sleep(1)

        raise RuntimeError("API 호출 최대 재시도 횟수 초과")

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        """응답에서 JSON을 추출하여 파싱."""
        # 코드블록 제거
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = re.sub(r"```", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # JSON 부분만 추출 시도
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.error(f"JSON 파싱 실패: {text[:200]}...")
            return None

    @staticmethod
    def _extract_section(text: str, section_name: str) -> str:
        """마크다운 응답에서 특정 섹션을 추출."""
        pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _fallback_clusters(articles: list[dict]) -> list[dict]:
        """클러스터링 실패 시 기본 클러스터 생성."""
        chunk_size = max(1, len(articles) // 10)
        clusters = []
        for i in range(10):
            start = i * chunk_size
            end = start + chunk_size if i < 9 else len(articles)
            chunk = articles[start:end]
            if not chunk:
                break
            clusters.append({
                "rank": i + 1,
                "topic_name": f"토픽 {i + 1}",
                "article_ids": [a["id"] for a in chunk],
                "brief": "",
            })
        return clusters
