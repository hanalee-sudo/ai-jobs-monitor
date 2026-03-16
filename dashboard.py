"""Streamlit 웹 대시보드: 토픽 기반 리포트 조회."""

import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import sys
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from storage.database import ArticleDatabase

# --- 페이지 설정 ---
st.set_page_config(
    page_title="AI와 일자리 마켓 인텔리전스",
    page_icon="📊",
    layout="wide",
)

# --- 비밀번호 보호 ---
DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "wantedlab2026")


def _check_password() -> bool:
    """비밀번호 확인. 통과하면 True 반환."""
    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 로그인")
    st.caption("접근 권한이 필요합니다.")
    password = st.text_input("비밀번호를 입력하세요", type="password")

    if st.button("로그인"):
        if password == DASHBOARD_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


# --- 데이터베이스 ---
db = ArticleDatabase()


def main():
    if not _check_password():
        return

    st.title("📊 AI와 일자리 마켓 인텔리전스")
    st.caption("원티드랩 | 채용 플랫폼 & AX 솔루션 관점 시장 동향 모니터링")

    # --- 리포트 목록 조회 ---
    reports = db.get_reports()

    if not reports:
        st.info(
            "생성된 리포트가 없습니다.\n\n"
            "터미널에서 다음 명령을 실행해주세요:\n"
            "1. `python main.py collect` (기사 수집)\n"
            "2. `python main.py report` (토픽 리포트 생성)"
        )
        _show_article_stats()
        return

    # --- 사이드바: 리포트 선택 ---
    with st.sidebar:
        st.header("📋 리포트 선택")

        report_options = {}
        for r in reports:
            date_str = r["created_date"][:10]
            label = f"{date_str} ({r['article_count']}건)"
            report_options[label] = r["id"]

        selected_label = st.selectbox("리포트", list(report_options.keys()))
        selected_report_id = report_options[selected_label]

        st.divider()
        _show_article_stats()

    # --- 선택된 리포트의 토픽 표시 ---
    selected_report = next(r for r in reports if r["id"] == selected_report_id)
    topics = db.get_report_topics(selected_report_id)

    st.markdown(
        f"**리포트 기간**: {selected_report['period_start'][:10]} ~ "
        f"{selected_report['period_end'][:10]} | "
        f"**분석 기사**: {selected_report['article_count']}건"
    )
    st.divider()

    if not topics:
        st.warning("이 리포트에 토픽이 없습니다.")
        return

    for topic in topics:
        _render_topic(topic)


def _render_topic(topic: dict):
    """토픽 카드를 렌더링."""
    rank = topic["rank"]
    icons = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    icon = icons[rank - 1] if rank <= 10 else f"#{rank}"

    st.subheader(f"{icon} {topic['topic_name']}")

    # 종합 요약
    if topic.get("topic_summary"):
        st.markdown("**📝 종합 요약**")
        st.markdown(topic["topic_summary"])

    # 핵심 인사이트
    if topic.get("key_insights"):
        st.markdown("**💡 핵심 인사이트**")
        st.markdown(topic["key_insights"])

    # 비즈니스 앵글
    if topic.get("business_angle"):
        st.markdown("**🎯 비즈니스 앵글**")
        st.markdown(topic["business_angle"])

    # 관련 기사 목록
    articles = db.get_topic_articles(topic["id"])
    if articles:
        with st.expander(f"📰 관련 기사 ({len(articles)}건)", expanded=False):
            for a in articles:
                pub_date = (a.get("published_date") or "")[:10]
                lang = "🇰🇷" if a.get("language") == "ko" else "🌐"
                if a.get("url"):
                    st.markdown(
                        f"- {lang} **{a['title']}** — {a['source_name']} ({pub_date}) "
                        f"[원문]({a['url']})"
                    )
                else:
                    st.markdown(
                        f"- {lang} **{a['title']}** — {a['source_name']} ({pub_date})"
                    )

    st.divider()


def _show_article_stats():
    """사이드바에 기사 통계 표시."""
    stats = db.get_stats()
    st.metric("전체 수집 기사", stats["total"])

    if stats["by_category"]:
        st.markdown("**카테고리별**")
        for cat, count in stats["by_category"].items():
            st.text(f"  {cat}: {count}건")


if __name__ == "__main__":
    main()
