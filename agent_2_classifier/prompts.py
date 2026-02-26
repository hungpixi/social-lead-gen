"""
Agent 2 — Prompt Templates.
Tập trung vào phân tích intent, không cần lọc spam/seeding phức tạp.
"""

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích cộng đồng online tại Việt Nam.

Nhiệm vụ: Phân tích comment trên mạng xã hội và xác định ý định (intent) thực sự của người dùng.

Lưu ý quan trọng:
- Người dùng MXH Việt Nam 2025 thường comment RẤT NGẮN (1-5 từ). Điều này KHÔNG có nghĩa là spam.
- "Quan tâm", "Follow", "Hay quá" — đều có thể là người dùng thật.
- Chỉ tập trung phân tích ý định, KHÔNG đánh giá đạo đức hay chất lượng con người.

Bạn PHẢI trả về đúng JSON format, không giải thích thêm."""


def build_classify_prompt(comment_text: str, post_content: str, response_type: str) -> str:
    """Tạo prompt phân tích cho 1 comment."""
    return f"""Phân tích comment sau đây:

── Bài viết gốc ──
{post_content[:300]}

── Comment ──
"{comment_text}"

── Phân loại phản hồi ──
{response_type} (SHORT = ≤5 từ, LONG = >5 từ)

Trả về JSON duy nhất:
{{
  "intent": "<một trong: JOIN_TEAM | ASK_QUESTION | SHARE_PAIN | OFFER_HELP | NOISE>",
  "quality_score": <0-100>,
  "insight": "<1 câu ngắn: người này muốn gì>",
  "suggested_action": "<1 câu: nên làm gì tiếp>"
}}

Hướng dẫn chấm điểm:
- JOIN_TEAM: Muốn tham gia, hợp tác, tìm nhóm → 70-100
- ASK_QUESTION: Hỏi cụ thể về kỹ năng, công cụ, cách làm → 50-80
- SHARE_PAIN: Chia sẻ khó khăn thực tế đang gặp → 60-90
- OFFER_HELP: Đề nghị giúp đỡ, chia sẻ tài nguyên → 40-70
- NOISE: Reaction đơn thuần, không có ý định rõ → 0-30"""


def build_batch_classify_prompt(items: list[dict]) -> str:
    """
    Tạo prompt phân tích nhiều comments cùng lúc (tiết kiệm API calls).
    Tối đa 5 comments/batch.
    """
    entries = []
    for i, item in enumerate(items[:5]):
        entries.append(
            f"[{i+1}] Post: {item['post_content'][:150]}\n"
            f"    Comment: \"{item['comment_text']}\"\n"
            f"    Type: {item['response_type']}"
        )

    items_text = "\n\n".join(entries)

    return f"""Phân tích {len(items[:5])} comments sau:

{items_text}

Trả về JSON array duy nhất (không giải thích):
[
  {{
    "index": 1,
    "intent": "JOIN_TEAM | ASK_QUESTION | SHARE_PAIN | OFFER_HELP | NOISE",
    "quality_score": 0-100,
    "insight": "1 câu ngắn",
    "suggested_action": "1 câu"
  }},
  ...
]"""
