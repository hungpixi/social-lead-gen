"""
Agent 1 — Cấu hình Crawler.
Chỉnh sửa file này để thêm/xoá groups và từ khoá theo dõi.
"""

# ─── Danh sách FB Groups cần theo dõi ───────────────────
# Thêm URL đầy đủ của group
GROUPS = [
    {
        "url": "https://www.facebook.com/groups/ketnoidoithi",
        "name": "Kết nối đô thị",
        "keywords": [],  # Lấy hết, không filter
    },
    # Thêm group mới ở đây:
    # {
    #     "url": "https://www.facebook.com/groups/...",
    #     "name": "Tên group",
    #     "keywords": ["keyword1", "keyword2"],
    # },
]

# ─── Settings ────────────────────────────────────────────
# Số bài viết tối đa quét mỗi lần (scroll)
MAX_POSTS_PER_SCAN = 20

# Số comment tối đa lấy mỗi bài viết
MAX_COMMENTS_PER_POST = 50

# Timeout cho mỗi thao tác (ms)
NAVIGATION_TIMEOUT = 30_000
SCROLL_DELAY_MS = 2_000

# ─── Facebook Default Avatar Hash ────────────────────────
# Hash của ảnh đại diện mặc định Facebook (male/female/group)
# Sẽ được cập nhật bởi avatar_checker.py
DEFAULT_AVATAR_HASHES = set()

# ─── User Agent ──────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
