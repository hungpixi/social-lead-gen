"""
Agent 3 — BizClaw Connector.
Kết nối với BizClaw Gateway API để gửi tin nhắn cá nhân hóa
qua Zalo, Telegram, Discord.
"""

import os
import json
import requests
from loguru import logger

from database.db import get_high_intent_leads


# ─── Config ──────────────────────────────────────────────
BIZCLAW_GATEWAY_URL = os.getenv("BIZCLAW_GATEWAY_URL", "http://127.0.0.1:3000")
BIZCLAW_PAIRING_CODE = os.getenv("BIZCLAW_PAIRING_CODE", "")


def _bizclaw_request(method: str, endpoint: str, data: dict = None) -> dict | None:
    """Gọi BizClaw Gateway API."""
    url = f"{BIZCLAW_GATEWAY_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if BIZCLAW_PAIRING_CODE:
        headers["X-Pairing-Code"] = BIZCLAW_PAIRING_CODE

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        else:
            resp = requests.post(url, headers=headers, json=data or {}, timeout=10)

        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"BizClaw API {resp.status_code}: {resp.text[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        logger.error(
            f"Không kết nối được BizClaw tại {BIZCLAW_GATEWAY_URL}. "
            "Hãy chắc chắn BizClaw đang chạy."
        )
        return None
    except Exception as e:
        logger.error(f"BizClaw request error: {e}")
        return None


# ─── Health Check ────────────────────────────────────────
def check_bizclaw_status() -> bool:
    """Kiểm tra BizClaw đang chạy hay không."""
    result = _bizclaw_request("GET", "/api/v1/info")
    if result:
        name = result.get("name", "BizClaw")
        version = result.get("version", "?")
        provider = result.get("default_provider", "?")
        logger.success(f"BizClaw OK: {name} v{version} (provider={provider})")
        return True
    return False


# ─── Chat / Send Message ────────────────────────────────
def send_message(channel: str, target_id: str, message: str) -> bool:
    """
    Gửi tin nhắn qua BizClaw.

    Args:
        channel: "zalo" | "telegram" | "discord"
        target_id: ID người nhận / group
        message: Nội dung tin nhắn
    """
    data = {
        "channel": channel,
        "target_id": target_id,
        "message": message,
    }
    result = _bizclaw_request("POST", "/api/chat/send", data)
    if result:
        logger.success(f"Sent to {channel}:{target_id[:20]}...")
        return True
    return False


def send_to_chat(message: str) -> dict | None:
    """
    Gửi message tới BizClaw để AI xử lý (chat mode).
    BizClaw sẽ trả lời dựa trên Identity đã cấu hình.
    """
    data = {"message": message}
    return _bizclaw_request("POST", "/api/chat", data)


# ─── Message Templates ──────────────────────────────────
def generate_outreach_message(lead: dict) -> str:
    """
    Tạo tin nhắn cá nhân hóa dựa trên insight từ Agent 2.
    """
    intent = lead.get("intent", "")
    insight = lead.get("insight", "")
    author = lead.get("author_name", "bạn")
    comment = lead.get("comment_text", "")[:100]

    templates = {
        "JOIN_TEAM": f"""Chào {author}! 👋

Mình thấy bạn có quan tâm đến việc tìm team. Mình đang build một cộng đồng về AI & Startup tại TP.HCM.

Nếu bạn muốn trao đổi thêm, mình có thể kết nối để chia sẻ thêm chi tiết nhé!""",

        "ASK_QUESTION": f"""Chào {author}! 👋

Mình thấy bạn đang tìm hiểu về chủ đề này. Mình có một số tài liệu và kinh nghiệm có thể chia sẻ.

"{comment[:60]}..."

Nếu bạn quan tâm, mình gửi thêm thông tin chi tiết nhé!""",

        "SHARE_PAIN": f"""Chào {author}! 👋

Mình hiểu vấn đề bạn đang gặp. Mình cũng đã trải qua điều tương tự và có một số giải pháp AI automation có thể giúp.

Bạn có muốn mình demo nhanh cách AI Agent xử lý bài toán này không?""",

        "OFFER_HELP": f"""Chào {author}! 👋

Mình thấy bạn có kinh nghiệm thú vị. Mình đang tìm kiếm những người có expertise trong lĩnh vực này để cùng phát triển dự án.

Liên hệ mình nếu bạn muốn kết nối nhé!""",
    }

    return templates.get(intent, f"Chào {author}! Mình thấy comment của bạn rất hay. Mình muốn kết nối!")


# ─── Process Leads ───────────────────────────────────────
def process_leads(
    min_score: int = 60,
    channel: str = "zalo",
    dry_run: bool = True,
) -> dict:
    """
    Xử lý leads chất lượng cao:
    - Tạo tin nhắn cá nhân hóa
    - Gửi qua BizClaw (nếu không phải dry_run)

    Args:
        min_score: Điểm tối thiểu để tiếp cận
        channel: Kênh gửi tin (zalo/telegram/discord)
        dry_run: True = chỉ xem trước, False = gửi thật
    """
    stats = {"total": 0, "sent": 0, "skipped": 0}
    leads = get_high_intent_leads(min_score=min_score)

    if not leads:
        logger.info("Không có leads mới cần liên hệ.")
        return stats

    logger.info(f"Processing {len(leads)} leads (dry_run={dry_run})...")

    for lead in leads:
        stats["total"] += 1
        message = generate_outreach_message(lead)

        if dry_run:
            print(f"\n{'─' * 50}")
            print(f"🎯 {lead['author_name']} | {lead['intent']} | Score: {lead['quality_score']}")
            print(f"📝 Comment: \"{lead['comment_text'][:80]}\"")
            print(f"💡 Insight: {lead['insight']}")
            print(f"📨 Tin nhắn sẽ gửi:")
            print(f"   {message[:150]}...")
            print(f"{'─' * 50}")
            stats["skipped"] += 1
        else:
            # Gửi thật qua BizClaw
            target_id = lead.get("author_profile_url", "")
            if target_id and send_message(channel, target_id, message):
                stats["sent"] += 1
                # Đánh dấu đã liên hệ
                from database.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE classified_leads SET contacted = 1 WHERE id = ?",
                    (lead["id"],),
                )
                conn.commit()
                conn.close()
            else:
                stats["skipped"] += 1
                logger.warning(f"Skip: {lead['author_name']} (no target_id)")

    logger.success(f"Agent 3 done: {stats}")
    return stats


# ─── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🔍 Checking BizClaw connection...")
    if check_bizclaw_status():
        process_leads(dry_run=True)
    else:
        print("❌ BizClaw chưa chạy. Hãy khởi động BizClaw trước.")
        print("   Chạy: d:\\business\\startup\\bizclaw\\target\\release\\bizclaw.exe")
