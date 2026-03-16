"""CLI 진입점: 기사 수집, 토픽 리포트 생성, 키워드 제안."""

import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    LOGS_DIR,
)


def setup_logging():
    """로깅 설정."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                LOGS_DIR / "pipeline.log", encoding="utf-8"
            ),
        ],
    )


def cmd_collect():
    """기사 수집 (AI 분석 없이 저장만)."""
    from pipeline.orchestrator import run_collect

    setup_logging()
    print("\n📥 기사 수집을 시작합니다...\n")
    stats = run_collect()
    print(f"\n✅ 수집 완료! 수집 {stats['collected']}건 → 신규 {stats['new']}건 → 저장 {stats['saved']}건")
    if stats["errors"]:
        print(f"⚠️  오류 {len(stats['errors'])}건 발생 (로그 확인)")


def cmd_report(days: int = 7):
    """토픽 리포트 생성."""
    from pipeline.orchestrator import run_report

    setup_logging()
    print(f"\n📊 토픽 리포트 생성 (최근 {days}일)...\n")
    result = run_report(days)

    if "error" in result:
        print(f"\n❌ {result['error']}")
        return

    print(f"\n✅ 리포트 생성 완료!")
    print(f"   리포트 ID: {result['report_id']}")
    print(f"   분석 기사: {result['article_count']}건")
    print(f"   생성 토픽: {result['topic_count']}개")
    print(f"\n💡 대시보드에서 확인: python run_dashboard.py")


def cmd_suggest_keywords():
    """키워드 업데이트 제안."""
    from pipeline.orchestrator import run_suggest_keywords

    setup_logging()
    print("\n🔑 키워드 업데이트 제안 (최근 30일 기사 분석)...\n")
    result = run_suggest_keywords()

    if "error" in result:
        print(f"\n❌ {result['error']}")
        return

    print("\n" + "=" * 50)
    print("📋 키워드 업데이트 제안")
    print("=" * 50)

    if result.get("add"):
        print("\n➕ 추가 추천 키워드:")
        for item in result["add"]:
            print(f"   • \"{item['keyword']}\" ({item.get('category', '')}) - {item['reason']}")

    if result.get("remove"):
        print("\n➖ 삭제 추천 키워드:")
        for item in result["remove"]:
            print(f"   • \"{item['keyword']}\" - {item['reason']}")

    if result.get("summary"):
        print(f"\n📝 종합 분석: {result['summary']}")

    print("\n💡 키워드를 변경하려면 config/sources.yaml 파일을 직접 수정해주세요.")


def cmd_test():
    """API 연결 테스트."""
    print("\n🧪 API 연결 테스트\n")
    all_ok = True

    # Anthropic API
    print("1. Anthropic Claude API...", end=" ")
    if ANTHROPIC_API_KEY:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=50,
                messages=[{"role": "user", "content": "Hello"}],
            )
            print(f"✅ 연결 성공 (모델: {CLAUDE_MODEL})")
        except Exception as e:
            print(f"❌ 실패: {e}")
            all_ok = False
    else:
        print("⚠️  API 키 미설정 (.env 파일 확인)")
        all_ok = False

    # RSS 피드 샘플
    print("2. RSS 피드 접근...", end=" ")
    try:
        import feedparser

        feed = feedparser.parse(
            "https://techcrunch.com/category/artificial-intelligence/feed/"
        )
        if feed.entries:
            print(f"✅ 성공 (TechCrunch: {len(feed.entries)}개 항목)")
        else:
            print("⚠️  피드는 접근 가능하나 항목 없음")
    except Exception as e:
        print(f"❌ 실패: {e}")
        all_ok = False

    print()
    if all_ok:
        print("✅ 모든 연결 테스트 통과!")
    else:
        print("⚠️  일부 테스트 실패. .env 파일을 확인해주세요.")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="AI와 일자리 마켓 인텔리전스 모니터링 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py test              API 연결 테스트
  python main.py collect           기사 수집 (매일 실행)
  python main.py report            최근 7일 토픽 리포트 생성
  python main.py report --days 14  최근 14일 토픽 리포트 생성
  python main.py suggest-keywords  키워드 업데이트 제안

대시보드 실행:
  python run_dashboard.py
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")

    subparsers.add_parser("collect", help="기사 수집 (AI 분석 없이)")
    subparsers.add_parser("test", help="API 연결 테스트")

    report_parser = subparsers.add_parser("report", help="토픽 리포트 생성")
    report_parser.add_argument(
        "--days", type=int, default=7, help="분석 기간 (일, 기본값: 7)"
    )

    subparsers.add_parser("suggest-keywords", help="키워드 업데이트 제안")

    # 하위 호환: run → collect
    subparsers.add_parser("run", help="기사 수집 (collect와 동일)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "collect" or args.command == "run":
        cmd_collect()
    elif args.command == "report":
        cmd_report(args.days)
    elif args.command == "suggest-keywords":
        cmd_suggest_keywords()
    elif args.command == "test":
        cmd_test()


if __name__ == "__main__":
    main()
