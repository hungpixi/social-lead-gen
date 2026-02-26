"""
Test Suite — Social Lead Gen Agent.
Chạy: python test_all.py
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

# Ensure project root in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

PASSED = 0
FAILED = 0

def test(name, func):
    global PASSED, FAILED
    try:
        func()
        print(f"  ✅ {name}")
        PASSED += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        FAILED += 1


# ═══════════════════════════════════════════════════════
# TEST 1: Database
# ═══════════════════════════════════════════════════════
print("\n🗄️  TEST 1: Database Layer")

def test_db_init():
    from database.db import init_db, get_db_path
    test_db = Path("data/test_leads.db")
    os.environ["DB_PATH"] = str(test_db)
    init_db()
    assert test_db.exists(), "DB file not created"

def test_db_save_comment():
    from database.db import save_comment
    result = save_comment(
        post_id="test_001",
        comment_text="Mình quan tâm, cho mình tham gia với!",
        author_name="Test User",
        author_profile_url="https://fb.com/testuser",
        post_content="Tìm team AI startup",
        source_group="Test Group",
    )
    assert result is not None, "save_comment returned None"

def test_db_save_duplicate():
    from database.db import save_comment
    result = save_comment(
        post_id="test_001",
        comment_text="Mình quan tâm, cho mình tham gia với!",
        author_name="Test User",
        author_profile_url="https://fb.com/testuser",
        post_content="Tìm team AI startup",
        source_group="Test Group",
    )
    assert result is None, "Duplicate should return None"

def test_db_batch_save():
    from database.db import save_comments_batch
    comments = [
        {"post_id": "test_002", "comment_text": "Hay quá", "author_name": "A", "source_group": "G1"},
        {"post_id": "test_002", "comment_text": "Follow", "author_name": "B", "source_group": "G1"},
        {"post_id": "test_003", "comment_text": "Mình đang tìm giải pháp AI cho công ty, có thể trao đổi thêm không?", "author_name": "C", "source_group": "G1"},
        {"post_id": "test_003", "comment_text": "Mình có kinh nghiệm làm chatbot, muốn join team", "author_name": "D", "source_group": "G1"},
        {"post_id": "test_004", "comment_text": "Ib", "author_name": "E", "source_group": "G1"},
    ]
    saved = save_comments_batch(comments)
    assert saved == 5, f"Expected 5, got {saved}"

def test_db_get_unanalyzed():
    from database.db import get_unanalyzed
    rows = get_unanalyzed(limit=10)
    assert len(rows) == 6, f"Expected 6 unanalyzed, got {len(rows)}"

def test_db_save_lead():
    from database.db import save_lead, get_unanalyzed
    rows = get_unanalyzed(limit=1)
    save_lead(
        comment_id=rows[0]["id"],
        response_type="LONG",
        intent="JOIN_TEAM",
        quality_score=85,
        insight="Người dùng muốn tham gia team",
        suggested_action="Kết nối ngay",
        model_used="test-model",
    )

def test_db_get_high_intent():
    from database.db import get_high_intent_leads
    leads = get_high_intent_leads(min_score=60)
    assert len(leads) >= 1, f"Expected >= 1 lead, got {len(leads)}"

def test_db_stats():
    from database.db import get_stats
    stats = get_stats()
    assert stats["total_comments"] == 6
    assert stats["analyzed"] == 1
    assert stats["pending"] == 5
    assert stats["high_intent"] >= 1

test("init_db", test_db_init)
test("save_comment", test_db_save_comment)
test("save_duplicate (skip)", test_db_save_duplicate)
test("batch_save", test_db_batch_save)
test("get_unanalyzed", test_db_get_unanalyzed)
test("save_lead", test_db_save_lead)
test("get_high_intent_leads", test_db_get_high_intent)
test("get_stats", test_db_stats)


# ═══════════════════════════════════════════════════════
# TEST 2: Agent 2 — Classifier (logic only, no API)
# ═══════════════════════════════════════════════════════
print("\n🧠 TEST 2: Classifier Logic")

def test_classify_short():
    from agent_2_classifier.classifier import classify_response_type
    assert classify_response_type("Quan tâm") == "SHORT"
    assert classify_response_type("Ib mình") == "SHORT"
    assert classify_response_type("Follow") == "SHORT"
    assert classify_response_type("Hay") == "SHORT"

def test_classify_long():
    from agent_2_classifier.classifier import classify_response_type
    assert classify_response_type("Mình đang tìm giải pháp AI cho công ty nhỏ") == "LONG"
    assert classify_response_type("Có thể chia sẻ thêm về kinh nghiệm làm chatbot không?") == "LONG"

def test_prompts_single():
    from agent_2_classifier.prompts import build_classify_prompt
    prompt = build_classify_prompt("quan tâm", "Tìm team AI", "SHORT")
    assert "quan tâm" in prompt
    assert "SHORT" in prompt
    assert "JSON" in prompt

def test_prompts_batch():
    from agent_2_classifier.prompts import build_batch_classify_prompt
    items = [
        {"post_content": "Tìm team", "comment_text": "ib mình", "response_type": "SHORT"},
        {"post_content": "AI Agent", "comment_text": "mình có kinh nghiệm", "response_type": "LONG"},
    ]
    prompt = build_batch_classify_prompt(items)
    assert "[1]" in prompt
    assert "[2]" in prompt

def test_parse_json():
    from agent_2_classifier.classifier import _parse_json_response
    # Normal JSON
    r = _parse_json_response('{"intent": "JOIN_TEAM", "quality_score": 80}')
    assert r["intent"] == "JOIN_TEAM"
    # JSON in markdown code block
    r = _parse_json_response('```json\n{"intent": "NOISE", "quality_score": 10}\n```')
    assert r["intent"] == "NOISE"
    # JSON with extra text
    r = _parse_json_response('Here is result: {"intent": "ASK_QUESTION", "quality_score": 50}')
    assert r["intent"] == "ASK_QUESTION"

test("classify SHORT responses", test_classify_short)
test("classify LONG responses", test_classify_long)
test("prompt template (single)", test_prompts_single)
test("prompt template (batch)", test_prompts_batch)
test("parse JSON (multiple formats)", test_parse_json)


# ═══════════════════════════════════════════════════════
# TEST 3: Agent 3 — BizClaw Connector
# ═══════════════════════════════════════════════════════
print("\n📨 TEST 3: BizClaw Connector")

def test_message_templates():
    from agent_3_bizclaw.connector import generate_outreach_message
    lead = {"intent": "JOIN_TEAM", "author_name": "Hưng", "comment_text": "join team", "insight": "test"}
    msg = generate_outreach_message(lead)
    assert "Hưng" in msg
    assert len(msg) > 20

def test_bizclaw_templates_all():
    from agent_3_bizclaw.connector import generate_outreach_message
    for intent in ["JOIN_TEAM", "ASK_QUESTION", "SHARE_PAIN", "OFFER_HELP"]:
        msg = generate_outreach_message({"intent": intent, "author_name": "Test", "comment_text": "test", "insight": ""})
        assert len(msg) > 20, f"Empty message for {intent}"

test("outreach message templates", test_message_templates)
test("all intent templates", test_bizclaw_templates_all)


# ═══════════════════════════════════════════════════════
# TEST 4: Agent 1 — Scraper (import only, no network)
# ═══════════════════════════════════════════════════════
print("\n🕷️  TEST 4: Scraper Imports")

def test_scraper_import():
    from agent_1_crawler.scraper import scrape_group, run_crawler, _extract_group_id
    assert callable(scrape_group)
    assert callable(run_crawler)

def test_extract_group_id():
    from agent_1_crawler.scraper import _extract_group_id
    assert _extract_group_id("https://www.facebook.com/groups/StartupVietnam") == "StartupVietnam"
    assert _extract_group_id("https://facebook.com/groups/123456789/") == "123456789"
    assert _extract_group_id("https://www.facebook.com/groups/AI.Vietnam?ref=share") == "AI.Vietnam"

def test_config():
    from agent_1_crawler.config import GROUPS, MAX_POSTS_PER_SCAN
    assert len(GROUPS) >= 2
    assert MAX_POSTS_PER_SCAN > 0

test("scraper imports", test_scraper_import)
test("extract group ID from URL", test_extract_group_id)
test("crawler config", test_config)


# ═══════════════════════════════════════════════════════
# TEST 5: OpenRouter API (live, optional)
# ═══════════════════════════════════════════════════════
print("\n🌐 TEST 5: OpenRouter API (live)")

def test_openrouter_classify():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("sk-or-v1-xxx"):
        raise Exception("SKIP — OPENROUTER_API_KEY not set")
    from agent_2_classifier.classifier import classify_single
    result = classify_single(
        "Mình đang tìm team AI startup, có thể join không?",
        "Tìm co-founder cho dự án AI Agent"
    )
    assert result is not None, "classify_single returned None"
    assert result["intent"] in ["JOIN_TEAM", "ASK_QUESTION", "SHARE_PAIN", "OFFER_HELP", "NOISE"]
    assert 0 <= result["quality_score"] <= 100
    print(f"       → Intent: {result['intent']}, Score: {result['quality_score']}")

test("OpenRouter classify (live)", test_openrouter_classify)


# ═══════════════════════════════════════════════════════
# Cleanup & Summary
# ═══════════════════════════════════════════════════════
print(f"\n{'=' * 50}")
print(f"📊 RESULTS: {PASSED} passed, {FAILED} failed")
print(f"{'=' * 50}")

# Cleanup test DB
test_db = Path("data/test_leads.db")
if test_db.exists():
    os.remove(test_db)
    # Also remove WAL/SHM files
    for ext in ["-wal", "-shm"]:
        wal = Path(str(test_db) + ext)
        if wal.exists():
            os.remove(wal)

# Reset DB_PATH
if "DB_PATH" in os.environ:
    os.environ["DB_PATH"] = "data/leads.db"

sys.exit(0 if FAILED == 0 else 1)
