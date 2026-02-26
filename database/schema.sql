-- ============================================
-- Social Lead Gen Agent — Database Schema
-- ============================================

-- Danh sách groups đang theo dõi
CREATE TABLE IF NOT EXISTS monitored_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    platform    TEXT NOT NULL DEFAULT 'facebook',   -- facebook | linkedin
    group_url   TEXT NOT NULL UNIQUE,
    group_name  TEXT,
    keywords    TEXT,                                -- JSON array: ["AI", "startup"]
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Dữ liệu thô từ Agent 1 (Crawler)
CREATE TABLE IF NOT EXISTS raw_comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id             TEXT,
    post_url            TEXT,
    post_content        TEXT,
    post_author         TEXT,
    comment_text        TEXT NOT NULL,
    author_name         TEXT,
    author_profile_url  TEXT,
    has_real_avatar     INTEGER DEFAULT 0,          -- 0=unknown, 1=real, -1=default
    comment_length      INTEGER,
    source_group        TEXT,
    scraped_at          DATETIME,
    analyzed            INTEGER DEFAULT 0,          -- 0=chưa, 1=đã phân tích
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, author_profile_url, comment_text)
);

-- Kết quả phân tích từ Agent 2 (Classifier)
CREATE TABLE IF NOT EXISTS classified_leads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id          INTEGER NOT NULL REFERENCES raw_comments(id),
    response_type       TEXT NOT NULL,               -- SHORT | LONG
    intent              TEXT,                         -- JOIN_TEAM | ASK_QUESTION | SHARE_PAIN | OFFER_HELP | NOISE
    quality_score       INTEGER DEFAULT 0,           -- 0-100
    insight             TEXT,
    suggested_action    TEXT,
    model_used          TEXT,                         -- deepseek/deepseek-r1
    contacted           INTEGER DEFAULT 0,           -- 0=chưa, 1=đã liên hệ
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index để query nhanh
CREATE INDEX IF NOT EXISTS idx_raw_analyzed ON raw_comments(analyzed);
CREATE INDEX IF NOT EXISTS idx_leads_intent ON classified_leads(intent);
CREATE INDEX IF NOT EXISTS idx_leads_score ON classified_leads(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_contacted ON classified_leads(contacted);
