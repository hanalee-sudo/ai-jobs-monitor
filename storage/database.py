"""SQLite 데이터베이스: 기사 저장 및 중복 방지."""

import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from collectors.base_collector import Article
from config.settings import DB_PATH

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

CREATE_ARTICLES_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE,
    title TEXT,
    url TEXT,
    source_name TEXT,
    category TEXT,
    published_date TEXT,
    collected_date TEXT,
    content_snippet TEXT,
    language TEXT,
    summary TEXT,
    insights TEXT,
    business_angle TEXT,
    review_status TEXT DEFAULT '대기중',
    notes TEXT DEFAULT ''
);
"""

CREATE_REPORTS_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_date TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    article_count INTEGER
);
"""

CREATE_TOPICS_SQL = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    topic_name TEXT NOT NULL,
    topic_summary TEXT,
    key_insights TEXT,
    business_angle TEXT,
    article_count INTEGER,
    FOREIGN KEY (report_id) REFERENCES reports(id)
);
"""

CREATE_TOPIC_ARTICLES_SQL = """
CREATE TABLE IF NOT EXISTS topic_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
"""


class ArticleDatabase:
    """SQLite 기반 기사 저장소."""

    def __init__(self):
        self.db_path = str(DB_PATH)
        self._init_db()

    def _init_db(self):
        """테이블이 없으면 생성."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_ARTICLES_SQL)
            conn.execute(CREATE_REPORTS_SQL)
            conn.execute(CREATE_TOPICS_SQL)
            conn.execute(CREATE_TOPIC_ARTICLES_SQL)
            conn.commit()

    @staticmethod
    def _url_hash(url: str) -> str:
        """URL의 SHA-256 해시 생성."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def is_seen(self, url: str) -> bool:
        """이미 저장된 URL인지 확인."""
        url_hash = self._url_hash(url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM articles WHERE url_hash = ?", (url_hash,)
            )
            return cursor.fetchone() is not None

    def filter_new(self, articles: list[Article]) -> list[Article]:
        """이미 저장된 기사를 제외하고 새 기사만 반환."""
        new_articles = []
        for article in articles:
            if not self.is_seen(article.url):
                new_articles.append(article)
        skipped = len(articles) - len(new_articles)
        if skipped > 0:
            logger.info(f"중복 기사 {skipped}건 건너뜀")
        return new_articles

    def save(self, article: Article):
        """기사를 DB에 저장."""
        url_hash = self._url_hash(article.url)
        now = datetime.now(KST).isoformat()
        pub_date = (
            article.published_date.isoformat()
            if article.published_date
            else now
        )

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """INSERT INTO articles
                    (url_hash, title, url, source_name, category,
                     published_date, collected_date, content_snippet,
                     language, summary, insights, business_angle)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        url_hash,
                        article.title,
                        article.url,
                        article.source_name,
                        article.category,
                        pub_date,
                        now,
                        article.content_snippet[:2000],
                        article.language,
                        article.summary,
                        article.insights,
                        article.business_angle,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                logger.debug(f"중복 저장 스킵: {article.title[:50]}")

    def save_batch(self, articles: list[Article]) -> int:
        """여러 기사를 저장하고 성공 건수 반환."""
        saved = 0
        for article in articles:
            try:
                self.save(article)
                saved += 1
            except Exception as e:
                logger.warning(f"저장 실패: {article.title[:50]}... → {e}")
        return saved

    def get_all(
        self,
        category: str | None = None,
        status: str | None = None,
        days: int | None = None,
    ) -> list[dict]:
        """기사 목록 조회 (필터 지원)."""
        query = "SELECT * FROM articles WHERE 1=1"
        params: list = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND review_status = ?"
            params.append(status)
        if days:
            cutoff = (datetime.now(KST) - timedelta(days=days)).isoformat()
            query += " AND collected_date >= ?"
            params.append(cutoff)

        query += " ORDER BY collected_date DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, article_id: int, status: str):
        """기사의 검토 상태를 변경."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE articles SET review_status = ? WHERE id = ?",
                (status, article_id),
            )
            conn.commit()

    def update_notes(self, article_id: int, notes: str):
        """기사에 메모를 추가."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE articles SET notes = ? WHERE id = ?",
                (notes, article_id),
            )
            conn.commit()

    def get_stats(self) -> dict:
        """통계 정보 반환."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            by_category = dict(
                conn.execute(
                    "SELECT category, COUNT(*) FROM articles GROUP BY category"
                ).fetchall()
            )
            by_status = dict(
                conn.execute(
                    "SELECT review_status, COUNT(*) FROM articles GROUP BY review_status"
                ).fetchall()
            )
            return {
                "total": total,
                "by_category": by_category,
                "by_status": by_status,
            }

    def cleanup_old(self, days: int = 90):
        """오래된 기사 삭제."""
        cutoff = (datetime.now(KST) - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM articles WHERE collected_date < ?", (cutoff,)
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"{result.rowcount}건의 오래된 기사 삭제됨")

    # --- 리포트 관련 메서드 ---

    def save_report(self, report_data: dict) -> int:
        """토픽 리포트를 저장하고 report_id를 반환."""
        now = datetime.now(KST).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO reports (created_date, period_start, period_end, article_count)
                VALUES (?, ?, ?, ?)""",
                (now, report_data["period_start"], report_data["period_end"],
                 report_data["article_count"]),
            )
            report_id = cursor.lastrowid

            for topic in report_data["topics"]:
                tc = conn.execute(
                    """INSERT INTO topics
                    (report_id, rank, topic_name, topic_summary,
                     key_insights, business_angle, article_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (report_id, topic["rank"], topic["topic_name"],
                     topic.get("topic_summary", ""),
                     topic.get("key_insights", ""),
                     topic.get("business_angle", ""),
                     len(topic.get("article_ids", []))),
                )
                topic_id = tc.lastrowid
                for article_id in topic.get("article_ids", []):
                    conn.execute(
                        "INSERT INTO topic_articles (topic_id, article_id) VALUES (?, ?)",
                        (topic_id, article_id),
                    )

            conn.commit()
            return report_id

    def get_reports(self) -> list[dict]:
        """모든 리포트 목록 조회 (최신순)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM reports ORDER BY created_date DESC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_report_topics(self, report_id: int) -> list[dict]:
        """리포트의 토픽 목록 조회 (rank순)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM topics WHERE report_id = ? ORDER BY rank",
                (report_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_topic_articles(self, topic_id: int) -> list[dict]:
        """토픽에 속한 기사 목록 조회."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT a.* FROM articles a
                JOIN topic_articles ta ON a.id = ta.article_id
                WHERE ta.topic_id = ?
                ORDER BY a.published_date DESC""",
                (topic_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
