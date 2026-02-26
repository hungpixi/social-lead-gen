# 🧠 Social Lead Gen Agent — AI-Powered Lead Generation from Facebook Groups

> **Một case study về xây dựng hệ thống AI Agent tự động hóa tác vụ outreach.**
> 
> Code là AI code giúp. Giá trị nằm ở **tư duy hệ thống, cách giải quyết vấn đề, và kiến trúc pipeline.**

---

## 🎯 Bài toán thực tế

Bạn đang khởi nghiệp. Bạn cần tìm khách hàng, đồng đội, đối tác. Bạn vào hàng chục Facebook Groups, scroll hàng trăm bài viết, đọc hàng ngàn comments... để tìm một người comment "ib mình ạ" hoặc "tìm team".

**Câu hỏi: Tại sao không để AI làm?**

## 🏗️ Kiến trúc — 3 AI Agents

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  AGENT 1         │───▶│  AGENT 2          │───▶│  AGENT 3         │
│  Crawler         │    │  Classifier       │    │  Outreach        │
│  (Playwright)    │    │  (DeepSeek R1)    │    │  (BizClaw+Gemini)│
│                  │    │                   │    │                  │
│  Scroll FB Group │    │  Phân loại intent │    │  Gửi tin nhắn    │
│  Click mở cmts   │    │  Chấm điểm lead   │    │  tự động qua     │
│  Extract text    │    │  Gợi ý action     │    │  Telegram/Zalo   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    SQLite DB              Classified Leads         Contacted Leads
```

## 💡 Quá trình tư duy & Giải quyết vấn đề

### Thử nghiệm 1: `facebook-scraper` (HTTP requests)

**Ý tưởng ban đầu**: Dùng thư viện `facebook-scraper` (3.1k ⭐ GitHub) — gọn, nhanh, không cần browser.

**Kết quả**: **0 posts.** Facebook đã chặn hoàn toàn HTTP scraping. Cookies hợp lệ, endpoint đúng, nhưng trả về trang trắng.

**Bài học**: Facebook liên tục cập nhật anti-scraping. Thư viện HTTP-based sẽ luôn "chạy đuổi" theo Facebook.

### Thử nghiệm 2: Playwright + CSS Selectors

**Ý tưởng**: Dùng browser thật (Playwright), giống user thật, Facebook không chặn được.

**Kết quả**: Login thành công ✅ nhưng... **0 posts.**

**Debug phát hiện**: `[role="article"]` chỉ chứa **Loading spinners**, không phải content. Selector `[data-ad-comet-preview="message"]` tìm được 3 elements nhưng Playwright Python `.query_selector()` trả về text rỗng.

**Root cause**: Facebook dùng **lazy virtualization** — DOM có element nhưng text chỉ render khi thực sự nhìn thấy trên viewport. Python selectors hoạt động trong context React virtual DOM, không thấy text thật.

### Thử nghiệm 3: `page.evaluate()` JavaScript thuần ✅

**Đột phá**: Thay vì dùng Python selectors, chạy JavaScript trực tiếp trong browser DOM:

```python
posts = page.evaluate("""
() => {
    const msgs = document.querySelectorAll('[data-ad-comet-preview="message"]');
    // ... extract trực tiếp trong browser context
}
""")
```

**Kết quả**: **6 posts** từ group đầu tiên! JavaScript `document.querySelectorAll()` hoạt động trong cùng context với React DOM, nên thấy được text thật.

### Thử nghiệm 4: Comment Extraction

**Vấn đề mới**: Lấy được posts nhưng comments ("ib nhé", "inbox giúp mình") nằm ẩn sau nút "View more comments".

**Giải pháp**: 
1. JS click tất cả nút "View more comments" / "Xem thêm bình luận"
2. Chờ Facebook load comments (2 giây)
3. Click lần 2 nếu có "View more replies"
4. JS extract từng comment riêng

**Kết quả**: **10 comments thật** từ 7 posts, bao gồm "ib mình ạ" và "Mình còn tuyển ko ạ" ✅

## 📊 So sánh: Trước vs Sau

| Tiêu chí | `facebook-scraper` | Playwright + JS evaluate |
|:---|:---|:---|
| **Posts extracted** | 0 ❌ | 7+ per group ✅ |
| **Comments** | 0 ❌ | 10+ (click expand) ✅ |
| **Anti-detection** | Bị chặn ngay | Giống user thật |
| **Lazy loading** | Không handle | JS evaluate vượt qua |
| **Maintenance** | Facebook update → hỏng | DOM-based, stable |
| **Cookie** | Netscape format only | JSON + Netscape + auto-save |

## 🔬 Kết quả thực tế — Group "Kết nối đô thị"

```
📝 7 posts crawled
💬 10 comments thật extracted
🧠 15 entries classified (0 errors)
🔥 11 HIGH INTENT leads

Top leads:
  [90] "Mình còn tuyển ko ạ" — Kimm Ngânn → ASK_QUESTION
  [85] "ib mình ạ"           — Lý Minh Anh → JOIN_TEAM  
  [95] Tìm dự án khởi nghiệp, AI Automation → JOIN_TEAM
```

Mỗi lead có: **📎 Link bài viết gốc** + **👤 Profile người comment** + **AI Insight** + **Suggested Action**.

## 🧩 Cải tiến kỹ thuật chính

### 1. JS Evaluate thay vì Python Selectors
Facebook React DOM + lazy virtualization = Python selectors vô dụng. JS evaluate chạy trong browser context → thấy mọi thứ user thấy.

### 2. Multi-tier URL Extraction
Facebook group posts không dùng URL cố định `/posts/`. Hệ thống dùng 3 tầng fallback:
- Pattern matching: `/posts/`, `/permalink/`, `pfbid`, `pcb.`
- Regex: `groups/[slug]/posts/[id]`  
- Timestamp links: `a[aria-label]` chứa `__cft__`

### 3. Click-to-Expand Comments
Không chỉ scroll — mà thực sự **click** vào "View more comments", chờ Facebook AJAX load xong, rồi mới extract. 2 lần click để bắt cả "View more replies".

### 4. Multi-model AI Classification
- **DeepSeek R1** (free tier, OpenRouter): classify intent  
- **Gemini 2.5 Flash** (free quota): outreach chat
- **Gemini 2.5 Pro** (nếu cần): complex tasks
- Ưu tiên free tier → chỉ dùng model mạnh khi cần

## 🚀 Hướng đi tương lai

1. **LinkedIn Integration** — Cùng pipeline, áp dụng cho LinkedIn Groups
2. **Auto-reply Agent** — BizClaw tự động comment/DM dựa trên template AI-generated
3. **Lead Scoring ML** — Train model riêng trên data thật thay vì rule-based
4. **Dashboard** — Web UI hiển thị leads real-time, filter theo group/intent/score
5. **Scheduled Crawling** — Cron job crawl mỗi 15 phút, push notification khi có hot lead
6. **Multi-platform** — Mở rộng ra Zalo Groups, Telegram Groups, Discord

## 🛠️ Quick Start

```bash
# Clone
git clone https://github.com/hungpixi/social-lead-gen.git
cd social-lead-gen

# Setup
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env  # Điền API keys

# Chạy
python main.py init       # Khởi tạo DB
python main.py run        # Crawl + Classify 1 lần
python main.py leads      # Xem top leads
python main.py loop       # Chạy liên tục 24/7
```

## 📁 Cấu trúc

```
social-lead-gen/
├── agent_1_crawler/     # Playwright scraper + JS evaluate
│   ├── scraper.py       # Core: scroll, click expand, extract
│   └── config.py        # Groups to monitor + keywords  
├── agent_2_classifier/  # DeepSeek R1 intent classification
│   ├── classifier.py    # Batch classify + score
│   └── prompts.py       # Prompt templates
├── agent_3_bizclaw/     # BizClaw outreach connector
│   └── connector.py     # Message templates + API
├── database/
│   ├── db.py            # SQLite operations
│   └── schema.sql       # 3 tables: groups, comments, leads
├── main.py              # CLI orchestrator
└── test_all.py          # 19 tests
```

## 🧠 Takeaway

> **Không phải tool nào có nhiều star cũng tốt.** `facebook-scraper` 3.1k ⭐ nhưng ngày nay trả về 0 results.
> 
> **Hiểu bản chất vấn đề quan trọng hơn viết code.** Khi biết Facebook dùng lazy virtualization, giải pháp JS evaluate xuất hiện tự nhiên.
> 
> **AI thay thế được giai đoạn coding, nhưng không thay thế được giai đoạn phân tích, debug, và ra quyết định.** 4 lần thử, 4 lần sai, mỗi lần debug sâu hơn → cuối cùng mới tìm đúng approach.

---

**Built by [Phạm Phú Nguyễn Hưng](https://github.com/hungpixi)** — Freelancer | AI Automation | Trading Bot  
*Part of [Comarai](https://comarai.com) — Companion for Marketing & AI Automation Agency*
