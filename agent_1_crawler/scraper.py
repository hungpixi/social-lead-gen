"""
Agent 1 — Facebook Group Scraper (Playwright + JS evaluate).
Dùng browser thật + JS evaluate trực tiếp để vượt qua Facebook lazy virtualization.
"""

import json
import os
import re
import time
from pathlib import Path

from loguru import logger

from agent_1_crawler.config import (
    MAX_POSTS_PER_SCAN,
    MAX_COMMENTS_PER_POST,
    SCROLL_DELAY_MS,
)
from database.db import save_comments_batch


# ─── Paths ────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COOKIE_PATH = DATA_DIR / "fb_cookies.json"
COOKIE_TXT_PATH = DATA_DIR / "fb_cookies.txt"


# ─── Cookie Management ───────────────────────────────────
def _parse_netscape_cookies(path: Path) -> list[dict]:
    cookies = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies.append({
                    "name": parts[5],
                    "value": parts[6],
                    "domain": parts[0],
                    "path": parts[2] if len(parts) > 2 else "/",
                    "secure": parts[3].upper() == "TRUE" if len(parts) > 3 else False,
                })
    return cookies


def _load_cookies() -> list[dict]:
    if COOKIE_PATH.exists():
        with open(COOKIE_PATH, "r") as f:
            return json.load(f)
    if COOKIE_TXT_PATH.exists():
        return _parse_netscape_cookies(COOKIE_TXT_PATH)
    return []


def _save_cookies(context) -> None:
    cookies = context.cookies()
    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIE_PATH, "w") as f:
        json.dump(cookies, f, indent=2)
    logger.info(f"Saved {len(cookies)} cookies")


# ─── Login ────────────────────────────────────────────────
def _ensure_login(page, context) -> bool:
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    url = page.url
    content = page.content()

    if "/login" in url or "login_form" in content:
        logger.warning("⚠️  Chưa login. Hãy login trong browser vừa mở...")
        for _ in range(24):
            time.sleep(5)
            if "/login" not in page.url and "checkpoint" not in page.url:
                logger.success("✅ Login thành công!")
                _save_cookies(context)
                return True
        logger.error("❌ Timeout login 120s.")
        return False

    logger.success("✅ Đã login Facebook.")
    _save_cookies(context)
    return True


# ─── Extract Posts (JS evaluate) ──────────────────────────
JS_EXTRACT_POSTS = """
() => {
    const msgs = document.querySelectorAll('[data-ad-comet-preview="message"]');
    const results = [];
    
    msgs.forEach((msgEl) => {
        const text = msgEl.innerText.trim();
        if (text.length < 3) return;
        
        // Walk up DOM to find post container
        let container = msgEl;
        for (let j = 0; j < 25; j++) {
            if (!container.parentElement) break;
            const parent = container.parentElement;
            const role = parent.getAttribute('role');
            if (role === 'feed' || role === 'main') break;
            container = parent;
        }
        
        // Author (first meaningful <strong>)
        let authorName = '';
        for (const s of container.querySelectorAll('strong')) {
            const t = s.innerText.trim();
            if (t.length > 1 && t.length < 50 && t !== 'Facebook') {
                authorName = t;
                break;
            }
        }
        
        // Author URL
        let authorUrl = '';
        for (const a of container.querySelectorAll('a[role="link"]')) {
            const href = a.href || '';
            if (href.includes('facebook.com/') && !href.includes('/groups/')) {
                authorUrl = href;
                break;
            }
        }
        
        // Post URL — nhiều dạng
        let postUrl = '';
        const urlPatterns = 'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"], a[href*="pcb."], a[href*="pfbid"]';
        const postLinks = container.querySelectorAll(urlPatterns);
        if (postLinks.length > 0) {
            postUrl = postLinks[0].href;
        }
        if (!postUrl) {
            for (const a of container.querySelectorAll('a[href*="/groups/"]')) {
                const href = a.href || '';
                if (href.match(/groups\\/[^/]+\\/posts\\/|groups\\/[^/]+\\/permalink\\/|pfbid/)) {
                    postUrl = href;
                    break;
                }
            }
        }
        if (!postUrl) {
            const timeLinks = container.querySelectorAll('a[aria-label]');
            for (const a of timeLinks) {
                const href = a.href || '';
                if (href.includes('/groups/') && href.includes('__cft__')) {
                    postUrl = href.split('?')[0];
                    break;
                }
            }
        }
        
        results.push({
            post_id: text.substring(0, 80),
            text: text.substring(0, 1000),
            author: authorName,
            author_url: authorUrl,
            post_url: postUrl,
        });
    });
    
    return results;
}
"""


# ─── Scroll and Collect Posts ─────────────────────────────
def _scroll_and_collect(page, max_posts: int = 20) -> list[dict]:
    """Scroll group + extract posts bằng JS evaluate."""
    time.sleep(5)  # Chờ FB render ban đầu

    collected_ids = set()
    all_posts = []

    for scroll_round in range(max_posts):
        page.evaluate(f"window.scrollTo(0, {(scroll_round + 1) * 600})")
        time.sleep(SCROLL_DELAY_MS / 1000 + 1)

        new_posts = page.evaluate(JS_EXTRACT_POSTS)

        for post in new_posts:
            pid = post["post_id"]
            if pid not in collected_ids:
                collected_ids.add(pid)
                all_posts.append({
                    "post_id": str(hash(pid)),
                    "post_text": post["text"],
                    "post_url": post["post_url"],
                    "post_author": post["author"],
                    "post_author_url": post["author_url"],
                })
                logger.debug(f"  📝 '{post['text'][:50]}...' by {post['author']}")

        if len(all_posts) >= max_posts:
            break

        at_bottom = page.evaluate(
            "window.innerHeight + window.scrollY >= document.body.scrollHeight - 200"
        )
        if at_bottom and scroll_round > 3:
            break

    return all_posts[:max_posts]


# ─── Click Expand Comments ────────────────────────────────
def _click_expand_comments(page, post_text_prefix: str) -> int:
    """Click 'View more comments' cho 1 post, trả về số nút đã click."""
    return page.evaluate("""
    (prefix) => {
        const msgs = document.querySelectorAll('[data-ad-comet-preview="message"]');
        let container = null;
        for (const msg of msgs) {
            if (msg.innerText.trim().substring(0, 40) === prefix.substring(0, 40)) {
                container = msg;
                for (let j = 0; j < 25; j++) {
                    if (!container.parentElement) break;
                    const p = container.parentElement;
                    if (p.getAttribute('role') === 'feed' || p.getAttribute('role') === 'main') break;
                    container = p;
                }
                break;
            }
        }
        if (!container) return 0;
        
        let clicked = 0;
        const btns = container.querySelectorAll('div[role="button"], span[role="button"]');
        for (const btn of btns) {
            const t = (btn.innerText || '').toLowerCase();
            if (t.includes('comment') || t.includes('bình luận') || 
                t.includes('view more') || t.includes('xem thêm') ||
                t.includes('view all') || t.includes('phản hồi') ||
                t.includes('more comment')) {
                try { btn.click(); clicked++; } catch(e) {}
            }
        }
        return clicked;
    }
    """, post_text_prefix)


# ─── Extract Comments (JS) ───────────────────────────────
JS_EXTRACT_COMMENTS = """
(postPrefix) => {
    const msgs = document.querySelectorAll('[data-ad-comet-preview="message"]');
    let postContainer = null;
    
    for (const msg of msgs) {
        if (msg.innerText.trim().substring(0, 40) === postPrefix.substring(0, 40)) {
            postContainer = msg;
            for (let j = 0; j < 25; j++) {
                if (!postContainer.parentElement) break;
                const parent = postContainer.parentElement;
                const role = parent.getAttribute('role');
                if (role === 'feed' || role === 'main') break;
                postContainer = parent;
            }
            break;
        }
    }
    
    if (!postContainer) return [];
    
    const results = [];
    const postText = postPrefix.substring(0, 30);
    const msgEl = postContainer.querySelector('[data-ad-comet-preview="message"]');
    
    // Approach 1: Tìm comments trong ul > li
    const commentLists = postContainer.querySelectorAll('ul');
    for (const ul of commentLists) {
        const items = ul.querySelectorAll(':scope > li, :scope > div');
        for (const item of items) {
            const spans = item.querySelectorAll('span[dir="auto"], div[dir="auto"]');
            let commentText = '';
            for (const span of spans) {
                const t = span.innerText.trim();
                // Bỏ qua UI text, giữ comments thật (kể cả ngắn như "ib", "quan tâm")
                if (t.length >= 2 && t !== 'Facebook' && !t.startsWith(postText) &&
                    t !== 'Like' && t !== 'Reply' && t !== 'Share' && t !== 'Send' &&
                    t !== 'Thích' && t !== 'Trả lời' && t !== 'Chia sẻ' && t !== 'Gửi' &&
                    !t.match(/^\\d+[hdwmy]$/) && !t.match(/^\\d+ (hour|day|week|month|year|giờ|ngày|tuần|tháng|năm)/) &&
                    t.length < 500) {
                    commentText = t;
                    break;
                }
            }
            if (!commentText || commentText.length < 2) continue;
            
            // Author
            let authorName = '', authorUrl = '';
            const links = item.querySelectorAll('a[role="link"]');
            for (const a of links) {
                const href = a.href || '';
                const name = a.innerText.trim();
                if (name.length > 1 && name.length < 50 && href.includes('facebook.com') && 
                    !href.includes('/groups/') && name !== 'Facebook') {
                    authorName = name;
                    authorUrl = href;
                    break;
                }
            }
            
            if (!results.some(r => r.text === commentText)) {
                results.push({text: commentText, author: authorName, author_url: authorUrl});
            }
        }
    }
    
    // Approach 2: Fallback — tìm tất cả dir=auto nằm NGOÀI message chính
    if (results.length === 0) {
        const allDirAuto = postContainer.querySelectorAll('div[dir="auto"], span[dir="auto"]');
        for (const el of allDirAuto) {
            if (msgEl && msgEl.contains(el)) continue;
            
            const t = el.innerText.trim();
            if (t.length < 2 || t === 'Facebook' || t.includes('Write') || 
                t === 'Like' || t === 'Reply' || t === 'Share' ||
                t === 'Thích' || t === 'Trả lời' || t === 'Chia sẻ' ||
                t === 'Comment' || t === 'Bình luận' ||
                t.match(/^\\d+[hdwmy]$/) || t.match(/^\\d+ (comment|bình luận)/) ||
                t.startsWith(postText)) continue;
            
            let authorName = '', authorUrl = '';
            let parent = el;
            for (let j = 0; j < 5; j++) {
                parent = parent.parentElement;
                if (!parent) break;
                const link = parent.querySelector('a[role="link"]');
                if (link) {
                    const name = link.innerText.trim();
                    if (name.length > 1 && name.length < 50 && name !== 'Facebook') {
                        authorName = name;
                        authorUrl = link.href || '';
                        break;
                    }
                }
            }
            
            if (!results.some(r => r.text === t) && t.length >= 2) {
                results.push({text: t, author: authorName, author_url: authorUrl});
            }
        }
    }
    
    return results;
}
"""


# ─── Scrape Group ────────────────────────────────────────
def scrape_group(group_id, group_name="", keywords=None, page_obj=None, context=None) -> int:
    all_comments = []
    group_url = f"https://www.facebook.com/groups/{group_id}/"

    logger.info(f"🕷️  Navigating to: {group_name or group_id}...")

    try:
        page_obj.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        page_text = page_obj.inner_text("body")[:500]
        if "isn't available" in page_text:
            logger.warning(f"Group {group_id} không tồn tại hoặc bạn chưa join.")
            return 0

        logger.info("📄 Scrolling and collecting posts...")
        posts = _scroll_and_collect(page_obj, max_posts=MAX_POSTS_PER_SCAN)
        logger.info(f"   Found {len(posts)} posts")

        for i, post in enumerate(posts):
            post_text = post["post_text"]

            if keywords and not any(kw.lower() in post_text.lower() for kw in keywords):
                continue

            # Bước 1: Click mở comments
            prefix = post_text[:40]
            clicked = _click_expand_comments(page_obj, prefix)
            if clicked > 0:
                time.sleep(2)  # Chờ FB load comments
                # Click lần 2 nếu có "View more replies"
                _click_expand_comments(page_obj, prefix)
                time.sleep(1.5)

            # Bước 2: Extract comments bằng JS
            comments = page_obj.evaluate(JS_EXTRACT_COMMENTS, prefix)
            if not isinstance(comments, list):
                comments = []

            for cmt in comments:
                if not cmt.get("text", "").strip():
                    continue
                all_comments.append({
                    "post_id": post["post_id"],
                    "post_url": post["post_url"],
                    "post_content": post_text[:500],
                    "post_author": post["post_author"],
                    "comment_text": cmt["text"],
                    "author_name": cmt["author"],
                    "author_profile_url": cmt["author_url"],
                    "has_real_avatar": 0,
                    "source_group": group_name or group_id,
                })

            logger.info(f"  Post {i+1}: {len(comments)} comments (clicked {clicked}) — '{post_text[:40]}...'")

            # Nếu post không có comments → lưu post content
            if not comments:
                all_comments.append({
                    "post_id": post["post_id"],
                    "post_url": post["post_url"],
                    "post_content": post_text[:500],
                    "post_author": post["post_author"],
                    "comment_text": post_text[:500],
                    "author_name": post["post_author"],
                    "author_profile_url": post["post_author_url"],
                    "has_real_avatar": 0,
                    "source_group": group_name or group_id,
                })

    except Exception as e:
        logger.error(f"Scrape error: {e}")

    saved = 0
    if all_comments:
        saved = save_comments_batch(all_comments)

    logger.success(f"Done: {group_name or group_id} — {len(posts)} posts, {len(all_comments)} cmt, {saved} new")
    return saved


# ─── Utils ────────────────────────────────────────────────
def _extract_group_id(url: str) -> str:
    match = re.search(r'facebook\.com/groups/([^/?&]+)', url)
    return match.group(1) if match else url.strip("/").split("/")[-1]


# ─── Run All Groups ──────────────────────────────────────
def run_crawler(groups=None) -> int:
    from playwright.sync_api import sync_playwright
    from agent_1_crawler.config import GROUPS as DEFAULT_GROUPS

    targets = groups or DEFAULT_GROUPS
    cookies = _load_cookies()
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            locale="vi-VN",
        )

        if cookies:
            context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies")

        page = context.new_page()

        if not _ensure_login(page, context):
            browser.close()
            return 0

        for group in targets:
            url = group.get("url") or group.get("group_url", "")
            name = group.get("name") or group.get("group_name", "")
            kw = group.get("keywords", [])
            if isinstance(kw, str):
                kw = json.loads(kw)

            group_id = _extract_group_id(url) if url else ""
            if not group_id:
                continue

            try:
                total += scrape_group(group_id, name, kw, page_obj=page, context=context)
            except Exception as e:
                logger.error(f"Failed {name}: {e}")

        _save_cookies(context)
        browser.close()

    return total


if __name__ == "__main__":
    total = run_crawler()
    print(f"\nTotal new comments: {total}")
