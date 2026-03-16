"""Claude API를 사용하여 기사를 분석하는 모듈."""

import logging
import re
import time

import anthropic

from analyzer.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from collectors.base_collector import Article
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MAX_TOKENS, CLAUDE_MODEL

logger = logging.getLogger(__name__)


class ClaudeAnalyzer:
    """Claude API로 기사를 분석하여 요약/인사이트/비즈니스앵글 생성."""

    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def analyze(self, article: Article) -> Article:
        """단일 기사를 분석하여 요약/인사이트/비즈니스앵글을 채움."""
        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=article.title,
            source_name=article.source_name,
            category=article.category,
            content_snippet=article.content_snippet[:2000],
        )

        response_text = self._call_api(user_prompt)

        # 응답 파싱
        article.summary = self._extract_section(response_text, "요약")
        article.insights = self._extract_section(response_text, "핵심 인사이트")
        article.business_angle = self._extract_section(response_text, "비즈니스 앵글")

        return article

    def analyze_batch(self, articles: list[Article]) -> list[Article]:
        """여러 기사를 순차적으로 분석."""
        analyzed = []
        total = len(articles)

        for i, article in enumerate(articles, 1):
            try:
                logger.info(f"분석 중 ({i}/{total}): {article.title[:50]}...")
                analyzed_article = self.analyze(article)
                analyzed.append(analyzed_article)
            except Exception as e:
                logger.warning(f"분석 실패: {article.title[:50]}... → {e}")
                # 분석 실패해도 기사 자체는 보존
                article.summary = "(분석 실패)"
                analyzed.append(article)

            # Rate limit 방지
            if i < total:
                time.sleep(0.5)

        return analyzed

    def _call_api(self, user_prompt: str, retries: int = 3) -> str:
        """Claude API 호출 (재시도 포함)."""
        for attempt in range(retries):
            try:
                message = self.client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=CLAUDE_MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return message.content[0].text
            except anthropic.RateLimitError:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Rate limit 도달. {wait}초 대기 후 재시도...")
                time.sleep(wait)
            except Exception as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"API 호출 실패 (시도 {attempt + 1}): {e}")
                time.sleep(1)

        raise RuntimeError("API 호출 최대 재시도 횟수 초과")

    @staticmethod
    def _extract_section(text: str, section_name: str) -> str:
        """마크다운 응답에서 특정 섹션을 추출."""
        pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
