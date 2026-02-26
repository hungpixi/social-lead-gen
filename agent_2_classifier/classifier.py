"""
Agent 2 — Classifier.
Kết nối OpenRouter free LLM để phân tích intent.
Chi phí: $0 (free tier models).
"""

import os
import json
import re
import time

import requests
from loguru import logger

from agent_2_classifier.prompts import (
    SYSTEM_PROMPT,
    build_classify_prompt,
    build_batch_classify_prompt,
)
from database.db import get_unanalyzed, save_lead


# ─── Config ──────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free models ưu tiên (thử lần lượt nếu model đầu fail)
FREE_MODELS = [
    "deepseek/deepseek-r1",
    "meta-llama/llama-4-maverick",
    "google/gemma-3-27b-it:free",
    "openrouter/auto",
]


def _get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        logger.error("OPENROUTER_API_KEY chưa được set trong .env")
    return key


# ─── Response Type ───────────────────────────────────────
def classify_response_type(comment: str) -> str:
    """Phân loại đơn giản: ngắn hay dài. Python thuần, $0."""
    return "SHORT" if len(comment.split()) <= 5 else "LONG"


# ─── OpenRouter API ──────────────────────────────────────
def _call_openrouter(user_prompt: str, model: str | None = None, retries: int = 2) -> str | None:
    """
    Gọi OpenRouter API.
    Tự retry với model khác nếu thất bại.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    models_to_try = [model] if model else FREE_MODELS.copy()

    for m in models_to_try:
        for attempt in range(retries):
            try:
                response = requests.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://social-lead-gen.local",
                        "X-Title": "Social Lead Gen Agent",
                    },
                    json={
                        "model": m,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug(f"Model {m} responded OK")
                    return content
                elif response.status_code == 429:
                    # Rate limited — chờ rồi thử lại
                    wait = 5 * (attempt + 1)
                    logger.warning(f"Rate limited on {m}. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    logger.warning(f"Model {m} returned {response.status_code}")
                    break  # Thử model khác

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on {m} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Error calling {m}: {e}")
                break

    logger.error("All models failed")
    return None


def _parse_json_response(raw: str) -> dict | list | None:
    """
    Parse JSON từ response LLM.
    Xử lý các trường hợp LLM trả thêm text rác.
    """
    # Tìm JSON trong response
    # Xử lý code block markdown
    cleaned = re.sub(r'```json\s*', '', raw)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    # Thử parse trực tiếp
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Tìm JSON object {...} hoặc array [...]
    for pattern in [r'\{[^{}]*\}', r'\[[\s\S]*\]']:
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    logger.warning(f"Could not parse JSON: {raw[:200]}")
    return None


# ─── Single Classification ──────────────────────────────
def classify_single(comment_text: str, post_content: str) -> dict | None:
    """Phân tích 1 comment."""
    response_type = classify_response_type(comment_text)
    prompt = build_classify_prompt(comment_text, post_content, response_type)
    raw = _call_openrouter(prompt)
    if not raw:
        return None

    result = _parse_json_response(raw)
    if result and isinstance(result, dict):
        result["response_type"] = response_type
        return result
    return None


# ─── Batch Classification ───────────────────────────────
def classify_batch(items: list[dict]) -> list[dict]:
    """
    Phân tích nhiều comments cùng lúc.
    Tiết kiệm API calls (1 call cho 5 comments).
    """
    # Thêm response_type cho mỗi item
    for item in items:
        item["response_type"] = classify_response_type(item["comment_text"])

    prompt = build_batch_classify_prompt(items)
    raw = _call_openrouter(prompt)
    if not raw:
        return []

    parsed = _parse_json_response(raw)
    if parsed and isinstance(parsed, list):
        # Gắn response_type vào kết quả
        for i, r in enumerate(parsed):
            if i < len(items):
                r["response_type"] = items[i]["response_type"]
        return parsed
    return []


# ─── Pipeline chính ─────────────────────────────────────
def run_classifier(batch_size: int = 5, limit: int = 50) -> dict:
    """
    Chạy classifier trên toàn bộ comments chưa phân tích.
    Returns: Thống kê kết quả.
    """
    stats = {"processed": 0, "saved": 0, "errors": 0, "by_intent": {}}

    unanalyzed = get_unanalyzed(limit=limit)
    if not unanalyzed:
        logger.info("No unanalyzed comments found")
        return stats

    logger.info(f"Processing {len(unanalyzed)} comments...")

    # Xử lý theo batch
    for i in range(0, len(unanalyzed), batch_size):
        batch = unanalyzed[i : i + batch_size]

        if len(batch) == 1:
            # Single mode
            item = batch[0]
            result = classify_single(item["comment_text"], item["post_content"] or "")
            if result:
                _save_result(item["id"], result, stats)
            else:
                stats["errors"] += 1
            stats["processed"] += 1
        else:
            # Batch mode
            results = classify_batch(batch)
            for j, result in enumerate(results):
                if j < len(batch):
                    _save_result(batch[j]["id"], result, stats)
            stats["processed"] += len(batch)
            if not results:
                stats["errors"] += len(batch)

        # Rate limit courtesy
        time.sleep(1)

    logger.success(
        f"Classification done: {stats['processed']} processed, "
        f"{stats['saved']} saved, {stats['errors']} errors"
    )
    return stats


def _save_result(comment_id: int, result: dict, stats: dict):
    """Lưu 1 kết quả phân tích vào DB."""
    try:
        intent = result.get("intent", "NOISE")
        score = int(result.get("quality_score", 0))

        save_lead(
            comment_id=comment_id,
            response_type=result.get("response_type", "SHORT"),
            intent=intent,
            quality_score=score,
            insight=result.get("insight", ""),
            suggested_action=result.get("suggested_action", ""),
            model_used=result.get("model", FREE_MODELS[0]),
        )

        stats["saved"] += 1
        stats["by_intent"][intent] = stats["by_intent"].get(intent, 0) + 1

    except Exception as e:
        logger.error(f"Save failed for comment {comment_id}: {e}")
        stats["errors"] += 1


# ─── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    result = run_classifier()
    print(json.dumps(result, indent=2, ensure_ascii=False))
