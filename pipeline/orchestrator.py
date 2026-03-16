"""메인 파이프라인: 수집/리포트/키워드 제안."""

import logging
from datetime import datetime, timedelta, timezone

from collectors.rss_collector import RSSCollector
from config.settings import load_sources
from storage.database import ArticleDatabase

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def run_collect() -> dict:
    """기사 수집만 실행 (AI 분석 없음).

    Returns:
        dict: {collected, new, saved, errors}
    """
    stats = {"collected": 0, "new": 0, "saved": 0, "errors": []}
    start_time = datetime.now(KST)
    logger.info("=" * 50)
    logger.info(f"기사 수집 시작: {start_time.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 50)

    # --- Step 1: 수집 ---
    logger.info("\n[Step 1] 데이터 수집")
    all_articles = []

    collectors = [
        ("RSS 피드", RSSCollector()),
    ]

    for name, collector in collectors:
        try:
            articles = collector.collect()
            all_articles.extend(articles)
            logger.info(f"  {name}: {len(articles)}건")
        except Exception as e:
            error_msg = f"{name} 수집 실패: {e}"
            logger.error(f"  {error_msg}")
            stats["errors"].append(error_msg)

    stats["collected"] = len(all_articles)
    logger.info(f"  총 수집: {stats['collected']}건")

    if not all_articles:
        logger.info("수집된 기사가 없습니다.")
        return stats

    # --- Step 2: 중복 제거 & 저장 ---
    logger.info("\n[Step 2] 중복 제거 & 저장")
    db = ArticleDatabase()
    new_articles = db.filter_new(all_articles)
    stats["new"] = len(new_articles)
    logger.info(f"  신규 기사: {stats['new']}건 (중복 제외: {stats['collected'] - stats['new']}건)")

    if new_articles:
        stats["saved"] = db.save_batch(new_articles)
        logger.info(f"  저장 완료: {stats['saved']}건")

    # --- 완료 ---
    elapsed = datetime.now(KST) - start_time
    logger.info(f"\n수집 완료 (소요: {elapsed.seconds}초)")
    logger.info(f"  수집: {stats['collected']} → 신규: {stats['new']} → 저장: {stats['saved']}")
    if stats["errors"]:
        logger.warning(f"  오류: {len(stats['errors'])}건")

    return stats


def run_report(days: int = 7) -> dict:
    """저장된 기사에서 토픽 리포트를 생성.

    Returns:
        dict: {report_id, topic_count, article_count, error}
    """
    from analyzer.topic_analyzer import TopicAnalyzer

    logger.info("=" * 50)
    logger.info(f"토픽 리포트 생성 (최근 {days}일)")
    logger.info("=" * 50)

    db = ArticleDatabase()
    articles = db.get_all(days=days)

    if not articles:
        msg = f"최근 {days}일 내 수집된 기사가 없습니다. 먼저 'python main.py collect'를 실행해주세요."
        logger.warning(msg)
        return {"error": msg}

    if len(articles) < 5:
        msg = f"기사가 {len(articles)}건뿐입니다. 최소 5건 이상 필요합니다."
        logger.warning(msg)
        return {"error": msg}

    logger.info(f"  대상 기사: {len(articles)}건")

    analyzer = TopicAnalyzer()
    report_data = analyzer.generate_report(articles, days)

    report_id = db.save_report(report_data)
    logger.info(f"\n리포트 저장 완료 (ID: {report_id})")

    return {
        "report_id": report_id,
        "topic_count": len(report_data["topics"]),
        "article_count": len(articles),
    }


def run_suggest_keywords() -> dict:
    """최근 30일 기사를 분석하여 키워드 추가/삭제를 제안.

    Returns:
        dict: {add, remove, summary}
    """
    from analyzer.topic_analyzer import TopicAnalyzer

    logger.info("=" * 50)
    logger.info("키워드 업데이트 제안")
    logger.info("=" * 50)

    db = ArticleDatabase()
    articles = db.get_all(days=30)

    if not articles:
        msg = "최근 30일 내 수집된 기사가 없습니다."
        logger.warning(msg)
        return {"error": msg}

    # 현재 키워드 로드 (RSS 카테고리에서 추출)
    sources = load_sources()
    current_keywords = []
    for category in sources.get("rss_feeds", {}).values():
        for feed in category:
            current_keywords.append(feed["name"])

    logger.info(f"  대상 기사: {len(articles)}건")
    logger.info(f"  현재 키워드: {len(current_keywords)}개")

    analyzer = TopicAnalyzer()
    result = analyzer.suggest_keywords(articles, current_keywords)

    logger.info(f"  추가 제안: {len(result.get('add', []))}개")
    logger.info(f"  삭제 제안: {len(result.get('remove', []))}개")

    return result


# 하위 호환: 기존 run_pipeline은 collect로 대체
def run_pipeline() -> dict:
    """기존 호환용: collect와 동일."""
    return run_collect()
