"""
Social Lead Gen Agent — Orchestrator.
Chạy Agent 1 (Crawler) → Agent 2 (Classifier) theo chu kỳ.
"""

import os
import sys
import time
import json
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load .env
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Copy từ example nếu chưa có
    example = Path(__file__).resolve().parent / ".env.example"
    if example.exists():
        import shutil
        shutil.copy(example, ENV_PATH)
        logger.warning(f"Đã tạo .env từ .env.example. Hãy điền API key vào {ENV_PATH}")
        load_dotenv(ENV_PATH)

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add(
    Path(__file__).resolve().parent / "data" / "logs" / "agent_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)

from database.db import init_db, get_stats, add_group, get_active_groups
from agent_1_crawler.scraper import run_crawler
from agent_2_classifier.classifier import run_classifier
from agent_3_bizclaw.connector import process_leads, check_bizclaw_status


# ─── Commands ────────────────────────────────────────────
def cmd_init():
    """Khởi tạo database và cấu hình ban đầu."""
    logger.info("🚀 Initializing Social Lead Gen Agent...")
    init_db()

    # Import groups từ config vào DB
    from agent_1_crawler.config import GROUPS
    for g in GROUPS:
        add_group(
            group_url=g["url"],
            group_name=g.get("name", ""),
            keywords=g.get("keywords", []),
        )
    logger.success("✅ Init complete!")


def cmd_stats():
    """Hiển thị thống kê."""
    stats = get_stats()
    print("\n" + "=" * 50)
    print("📊 SOCIAL LEAD GEN — THỐNG KÊ")
    print("=" * 50)
    print(f"  📝 Tổng comments thu thập : {stats['total_comments']}")
    print(f"  ✅ Đã phân tích           : {stats['analyzed']}")
    print(f"  ⏳ Chờ phân tích          : {stats['pending']}")
    print(f"  🎯 Leads tổng             : {stats['total_leads']}")
    print(f"  🔥 High Intent (≥60)      : {stats['high_intent']}")
    print(f"  📤 Đã liên hệ            : {stats['contacted']}")
    print("=" * 50 + "\n")


def cmd_leads():
    """Hiển thị leads chất lượng cao."""
    from database.db import get_high_intent_leads
    leads = get_high_intent_leads(min_score=50)
    if not leads:
        print("Chưa có leads nào. Hãy chạy 'crawl' và 'classify' trước.")
        return

    print(f"\n🔥 TOP LEADS ({len(leads)} người)")
    print("-" * 60)
    for lead in leads[:20]:
        emoji = {"JOIN_TEAM": "🤝", "ASK_QUESTION": "❓", "SHARE_PAIN": "😣", "OFFER_HELP": "🙋"}.get(lead["intent"], "📌")
        print(f"\n{emoji} [{lead['quality_score']}/100] {lead['author_name']}")
        print(f"   Intent: {lead['intent']}")
        print(f"   Comment: \"{lead['comment_text'][:80]}\"")
        print(f"   Insight: {lead['insight']}")
        print(f"   Action: {lead['suggested_action']}")
        if lead.get("post_url"):
            print(f"   📎 Post: {lead['post_url']}")
        if lead["author_profile_url"]:
            print(f"   👤 Profile: {lead['author_profile_url']}")


def cmd_crawl():
    """Chạy Agent 1 — Crawler."""
    logger.info("🕷️  Agent 1: Starting Crawler...")
    total = run_crawler()
    logger.success(f"🕷️  Agent 1: Done — {total} new comments")
    return total


def cmd_classify():
    """Chạy Agent 2 — Classifier."""
    logger.info("🧠 Agent 2: Starting Classifier...")
    result = run_classifier(batch_size=5, limit=100)
    logger.success(f"🧠 Agent 2: Done — {json.dumps(result, ensure_ascii=False)}")
    return result


def cmd_run():
    """Chạy cả 2 Agent tuần tự (1 lần)."""
    cmd_crawl()
    cmd_classify()
    cmd_stats()


def cmd_loop():
    """Chạy liên tục theo chu kỳ."""
    interval = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "15"))
    logger.info(f"🔄 Loop mode: chạy mỗi {interval} phút. Ctrl+C để dừng.")

    while True:
        try:
            cmd_run()
            logger.info(f"💤 Chờ {interval} phút...")
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            logger.info("👋 Dừng loop.")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)  # Chờ 1 phút rồi thử lại


def cmd_outreach(dry_run: bool = True):
    """Chạy Agent 3 — BizClaw Outreach."""
    logger.info("📨 Agent 3: Starting Outreach...")
    result = process_leads(min_score=60, dry_run=dry_run)
    logger.success(f"📨 Agent 3: Done — {json.dumps(result, ensure_ascii=False)}")
    return result


def cmd_bizclaw_status():
    """Kiểm tra BizClaw connection."""
    if check_bizclaw_status():
        print("✅ BizClaw đang chạy.")
    else:
        print("❌ BizClaw chưa chạy.")
        print("   Chạy: d:\\business\\startup\\bizclaw\\target\\release\\bizclaw.exe")


# ─── CLI ─────────────────────────────────────────────────
USAGE = """
╔═══════════════════════════════════════════════════════╗
║          SOCIAL LEAD GEN AGENT — CLI                  ║
╠═══════════════════════════════════════════════════════╣
║  python main.py init       Khởi tạo database          ║
║  python main.py crawl      Cào dữ liệu 1 lần          ║
║  python main.py classify   Phân tích leads             ║
║  python main.py run        Crawl + Classify 1 lần      ║
║  python main.py loop       Chạy liên tục 24/7          ║
║  python main.py stats      Xem thống kê                ║
║  python main.py leads      Xem top leads               ║
║  python main.py outreach   Xem trước tin nhắn (dry)    ║
║  python main.py send       Gửi tin thật qua BizClaw    ║
║  python main.py bizclaw    Kiểm tra BizClaw status     ║
╚═══════════════════════════════════════════════════════╝
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return

    command = sys.argv[1].lower()

    if command == "init":
        cmd_init()
    elif command == "stats":
        cmd_stats()
    elif command == "leads":
        cmd_leads()
    elif command == "crawl":
        cmd_crawl()
    elif command == "classify":
        cmd_classify()
    elif command == "run":
        cmd_run()
    elif command == "loop":
        cmd_loop()
    elif command == "outreach":
        cmd_outreach(dry_run=True)
    elif command == "send":
        cmd_outreach(dry_run=False)
    elif command == "bizclaw":
        cmd_bizclaw_status()
    else:
        print(f"Unknown command: {command}")
        print(USAGE)


if __name__ == "__main__":
    main()
