"""기사 데이터 모델 및 수집기 베이스 클래스."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """수집된 기사 하나를 표현하는 데이터 클래스."""

    title: str
    url: str
    source_name: str
    category: str  # "채용/HR", "AI/기술", "정부정책"
    published_date: datetime
    content_snippet: str = ""  # 본문 앞부분 (최대 2000자)
    language: str = "ko"  # "ko" 또는 "en"
    # AI 분석 결과 (분석 후 채워짐)
    summary: str = ""
    insights: str = ""
    business_angle: str = ""


class BaseCollector(ABC):
    """모든 수집기의 추상 베이스 클래스."""

    @abstractmethod
    def collect(self) -> list[Article]:
        """데이터 소스에서 기사를 수집하여 반환."""
        pass
