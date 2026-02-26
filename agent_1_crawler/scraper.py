"""
Agent 1 — Facebook Group Scraper.
Sử dụng thư viện facebook-scraper (3.1k ⭐ trên GitHub).
Repo: https://github.com/kevinzg/facebook-scraper

Chi phí: $0 (không cần API key).
"""

import json
import os
from pathlib import Path
from datetime import datetime

from loguru import logger

try:
    from facebook_scraper import (
        get_posts,
        get_group_info,
        get_profile,
        set_cookies,
        enable_logging,
    )
except ImportError:
    logger.error("Chưa cài facebook-scraper. Chạy: pip install facebook-scraper")
    raise

from agent_1_crawler.config import (
    MAX_POSTS_PER_SCAN,
    MAX_COMMENTS_PER_POST,
)
from database.db import save_comments_batch


# ─── Cookie Management ───────────────────────────────────
COOKIE_PATH = Path(__file__).resolve().parent.parent / "data" / "fb_cookies.txt"


def _load_cookies() -> str | None:
    """Load cookies từ file (Netscape format hoặc JSON)."""
    if COOKIE_PATH.exists():
        logger.info(f"Loading cookies from {COOKIE_PATH}")
        return str(COOKIE_PATH)
    # Thử tự động lấy từ browser
    logger.info("No cookie file found. Trying 'from_browser'...")
    return "from_browser"


# ─── Scrape Group ────────────────────────────────────────
def scrape_group(
    group_id: str,
    group_name: str = "",
    keywords: list[str] | None = None,
    pages: int = 3,
    cookies: str | None = None,
) -> int:
    """
    Cào posts + comments từ 1 Facebook Group.

    Args:
        group_id: ID hoặc tên group (ví dụ: "StartupVietnam" hoặc "123456789")
        group_name: Tên hiển thị
        keywords: Lọc bài viết theo từ khoá (optional)
        pages: Số trang cần quét (mỗi trang ~4 posts mặc định)
        cookies: Đường dẫn file cookies hoặc "from_browser"

    Returns:
        Số comments đã lưu mới.
    """
    cookie_source = cookies or _load_cookies()
    all_comments = []

    logger.info(f"🕷️  Scraping group: {group_name or group_id} ({pages} pages)...")

    try:
        post_count = 0
        for post in get_posts(
            group=group_id,
            pages=pages,
            cookies=cookie_source,
            options={
                "comments": MAX_COMMENTS_PER_POST,
                "allow_extra_requests": True,
                "posts_per_page": 10,
            },
            timeout=30,
        ):
            post_count += 1
            if post_count > MAX_POSTS_PER_SCAN:
                break

            post_text = post.get("text") or post.get("post_text") or ""

            # Lọc theo keywords (nếu có)
            if keywords:
                combined = (post_text + " " + str(post.get("comments", ""))).lower()
                if not any(kw.lower() in combined for kw in keywords):
                    continue

            post_id = post.get("post_id") or f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}_{post_count}"
            post_url = post.get("post_url") or ""
            post_author = post.get("username") or post.get("user_id") or ""

            # Lấy comments
            comments_data = post.get("comments_full") or []
            if not comments_data:
                # Nếu không có comments_full, thử comments
                comments_data = post.get("comments") or []

            for comment in comments_data:
                comment_text = ""
                author_name = ""
                author_url = ""

                if isinstance(comment, dict):
                    comment_text = comment.get("comment_text") or ""
                    author_name = comment.get("commenter_name") or ""
                    commenter_url = comment.get("commenter_url") or ""
                    author_url = commenter_url
                elif isinstance(comment, str):
                    comment_text = comment

                if not comment_text.strip():
                    continue

                all_comments.append({
                    "post_id": str(post_id),
                    "post_url": str(post_url),
                    "post_content": post_text[:500],
                    "post_author": str(post_author),
                    "comment_text": comment_text.strip(),
                    "author_name": author_name,
                    "author_profile_url": author_url,
                    "has_real_avatar": 0,
                    "source_group": group_name or group_id,
                })

            logger.debug(
                f"Post {post_count}: {len(comments_data)} comments "
                f"('{post_text[:50]}...')"
            )

    except Exception as e:
        logger.error(f"Scrape error for {group_name or group_id}: {e}")
        if "cookies" in str(e).lower() or "login" in str(e).lower():
            logger.warning(
                "⚠️  Cookie lỗi/hết hạn. Hãy export cookies từ trình duyệt:\n"
                "   1. Cài extension 'Get cookies.txt LOCALLY' trên Chrome\n"
                "   2. Vào facebook.com, click extension → Export\n"
                f"   3. Lưu file vào: {COOKIE_PATH}"
            )

    # Lưu vào DB
    saved = 0
    if all_comments:
        saved = save_comments_batch(all_comments)

    logger.success(
        f"Done: {group_name or group_id} — "
        f"{post_count} posts, {len(all_comments)} comments, {saved} new saved"
    )
    return saved


# ─── Scrape Group Info ───────────────────────────────────
def get_group_details(group_id: str, cookies: str | None = None) -> dict:
    """Lấy thông tin tổng quan của group."""
    cookie_source = cookies or _load_cookies()
    try:
        info = get_group_info(group_id, cookies=cookie_source)
        logger.info(f"Group info: {info.get('name', group_id)} — {info.get('members', '?')} members")
        return info
    except Exception as e:
        logger.error(f"Get group info failed: {e}")
        return {}


# ─── Scrape Profile ─────────────────────────────────────
def get_user_profile(username: str, cookies: str | None = None) -> dict:
    """Lấy thông tin profile của 1 user."""
    cookie_source = cookies or _load_cookies()
    try:
        profile = get_profile(username, cookies=cookie_source)
        return profile
    except Exception as e:
        logger.error(f"Get profile failed for {username}: {e}")
        return {}


# ─── Run All Groups ──────────────────────────────────────
def run_crawler(groups: list[dict] | None = None) -> int:
    """
    Chạy crawler cho tất cả groups.
    Returns: Tổng số comments mới.
    """
    from database.db import get_active_groups
    from agent_1_crawler.config import GROUPS as DEFAULT_GROUPS

    targets = groups or []
    if not targets:
        db_groups = get_active_groups()
        if db_groups:
            targets = db_groups
        else:
            targets = DEFAULT_GROUPS

    total = 0
    for group in targets:
        url = group.get("url") or group.get("group_url", "")
        name = group.get("name") or group.get("group_name", "")
        keywords = group.get("keywords", [])
        if isinstance(keywords, str):
            keywords = json.loads(keywords)

        # Trích xuất group ID từ URL
        group_id = _extract_group_id(url) if url else ""
        if not group_id:
            logger.warning(f"Cannot extract group ID from: {url}")
            continue

        try:
            saved = scrape_group(group_id, name, keywords)
            total += saved
        except Exception as e:
            logger.error(f"Failed to scrape {name}: {e}")
            continue

    return total


def _extract_group_id(url: str) -> str:
    """Trích xuất group ID/name từ URL Facebook."""
    import re
    # https://www.facebook.com/groups/StartupVietnam → StartupVietnam
    # https://www.facebook.com/groups/123456789 → 123456789
    match = re.search(r'facebook\.com/groups/([^/?&]+)', url)
    if match:
        return match.group(1)
    return url.strip("/").split("/")[-1]


# ─── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    total = run_crawler()
    print(f"\nTotal new comments: {total}")
