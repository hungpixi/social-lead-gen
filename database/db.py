"""
Database Layer — CRUD operations cho Social Lead Gen Agent.
Sử dụng SQLite (miễn phí, không cần server).
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from loguru import logger


# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB_PATH = BASE_DIR / "data" / "leads.db"


def get_db_path() -> Path:
    """Lấy đường dẫn DB từ env hoặc mặc định."""
    path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Tạo connection tới SQLite."""
    db = db_path or get_db_path()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row  # Trả về dict-like rows
    conn.execute("PRAGMA journal_mode=WAL")  # Tăng performance ghi
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Init ────────────────────────────────────────────────
def init_db(db_path: Path | None = None):
    """Tạo toàn bộ tables từ schema.sql."""
    conn = get_connection(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()
    logger.success(f"Database initialized at {db_path or get_db_path()}")


# ─── Monitored Groups ───────────────────────────────────
def add_group(group_url: str, group_name: str = "", keywords: list[str] | None = None,
              platform: str = "facebook") -> int:
    """Thêm group cần theo dõi."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO monitored_groups (platform, group_url, group_name, keywords)
               VALUES (?, ?, ?, ?)""",
            (platform, group_url, group_name, json.dumps(keywords or []))
        )
        conn.commit()
        logger.info(f"Added group: {group_name or group_url}")
        return cursor.lastrowid
    finally:
        conn.close()


def get_active_groups() -> list[dict]:
    """Lấy danh sách groups đang active."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM monitored_groups WHERE is_active = 1"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["keywords"] = json.loads(d["keywords"]) if d["keywords"] else []
            result.append(d)
        return result
    finally:
        conn.close()


# ─── Raw Comments (Agent 1 ghi) ─────────────────────────
def save_comment(
    post_id: str,
    comment_text: str,
    author_name: str = "",
    author_profile_url: str = "",
    post_url: str = "",
    post_content: str = "",
    post_author: str = "",
    has_real_avatar: int = 0,
    source_group: str = "",
) -> int | None:
    """Lưu 1 comment thô. Trả về ID hoặc None nếu trùng."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO raw_comments
               (post_id, post_url, post_content, post_author,
                comment_text, author_name, author_profile_url,
                has_real_avatar, comment_length, source_group, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post_id, post_url, post_content, post_author,
                comment_text, author_name, author_profile_url,
                has_real_avatar, len(comment_text.split()),
                source_group, datetime.now().isoformat(),
            ),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return cursor.lastrowid
        return None  # Trùng lặp
    finally:
        conn.close()


def save_comments_batch(comments: list[dict]) -> int:
    """Lưu nhiều comments cùng lúc. Trả về số lượng đã lưu."""
    conn = get_connection()
    saved = 0
    try:
        for c in comments:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO raw_comments
                   (post_id, post_url, post_content, post_author,
                    comment_text, author_name, author_profile_url,
                    has_real_avatar, comment_length, source_group, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    c.get("post_id", ""),
                    c.get("post_url", ""),
                    c.get("post_content", ""),
                    c.get("post_author", ""),
                    c["comment_text"],
                    c.get("author_name", ""),
                    c.get("author_profile_url", ""),
                    c.get("has_real_avatar", 0),
                    len(c["comment_text"].split()),
                    c.get("source_group", ""),
                    datetime.now().isoformat(),
                ),
            )
            if cursor.rowcount > 0:
                saved += 1
        conn.commit()
        logger.info(f"Saved {saved}/{len(comments)} comments (duplicates skipped)")
        return saved
    finally:
        conn.close()


def get_unanalyzed(limit: int = 50) -> list[dict]:
    """Lấy comments chưa được Agent 2 phân tích."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, post_id, post_content, comment_text,
                      author_name, author_profile_url, has_real_avatar,
                      comment_length, source_group
               FROM raw_comments
               WHERE analyzed = 0
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_analyzed(comment_id: int):
    """Đánh dấu comment đã xử lý."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE raw_comments SET analyzed = 1 WHERE id = ?",
            (comment_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Classified Leads (Agent 2 ghi) ─────────────────────
def save_lead(
    comment_id: int,
    response_type: str,
    intent: str,
    quality_score: int,
    insight: str = "",
    suggested_action: str = "",
    model_used: str = "",
):
    """Lưu kết quả phân tích của Agent 2."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO classified_leads
               (comment_id, response_type, intent, quality_score,
                insight, suggested_action, model_used)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (comment_id, response_type, intent, quality_score,
             insight, suggested_action, model_used),
        )
        conn.commit()
        mark_analyzed(comment_id)
    finally:
        conn.close()


def get_high_intent_leads(min_score: int = 60) -> list[dict]:
    """Lấy leads chất lượng cao chưa được liên hệ."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT cl.*, rc.author_name, rc.author_profile_url,
                      rc.comment_text, rc.post_content, rc.source_group
               FROM classified_leads cl
               JOIN raw_comments rc ON cl.comment_id = rc.id
               WHERE cl.quality_score >= ?
                 AND cl.intent != 'NOISE'
                 AND cl.contacted = 0
               ORDER BY cl.quality_score DESC""",
            (min_score,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """Thống kê tổng quan."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM raw_comments").fetchone()[0]
        analyzed = conn.execute(
            "SELECT COUNT(*) FROM raw_comments WHERE analyzed = 1"
        ).fetchone()[0]
        leads = conn.execute("SELECT COUNT(*) FROM classified_leads").fetchone()[0]
        high_intent = conn.execute(
            "SELECT COUNT(*) FROM classified_leads WHERE quality_score >= 60 AND intent != 'NOISE'"
        ).fetchone()[0]
        contacted = conn.execute(
            "SELECT COUNT(*) FROM classified_leads WHERE contacted = 1"
        ).fetchone()[0]
        return {
            "total_comments": total,
            "analyzed": analyzed,
            "pending": total - analyzed,
            "total_leads": leads,
            "high_intent": high_intent,
            "contacted": contacted,
        }
    finally:
        conn.close()
