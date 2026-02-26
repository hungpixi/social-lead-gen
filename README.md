# Social Lead Gen Agent 🤖

AI-powered social media lead generation system cho community building tại Việt Nam.

> Thu thập comments từ Facebook Groups → AI phân tích intent → Tự động kết nối qua BizClaw (Zalo/Telegram/Discord)

## 🏗️ Architecture

```
┌──────────┐    ┌──────────────┐    ┌───────────────┐
│ Agent 1  │───▶│   Agent 2    │───▶│   Agent 3     │
│ CRAWLER  │    │  CLASSIFIER  │    │  CONNECTOR    │
│(fb-scraper)   │(OpenRouter)  │    │  (BizClaw)    │
└──────────┘    └──────────────┘    └───────────────┘
```

| Agent | Công nghệ | Chi phí |
|:---|:---|:---|
| Crawler | [facebook-scraper](https://github.com/kevinzg/facebook-scraper) (3.1k ⭐) | $0 |
| Classifier | OpenRouter free LLM (DeepSeek R1, Llama 4) | $0 |
| Connector | [BizClaw](https://bizclaw.vn) (Zalo/Telegram/Discord) | $0 |
| Database | SQLite | $0 |

**Tổng chi phí: ~$0-1/tháng** (chỉ captcha nếu cần)

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/social-lead-gen.git
cd social-lead-gen

# 2. Install
pip install -r requirements.txt

# 3. Config
cp .env.example .env
# Điền OPENROUTER_API_KEY (free tại openrouter.ai/keys)

# 4. Init database
python main.py init

# 5. Run
python main.py crawl      # Cào dữ liệu
python main.py classify   # AI phân tích
python main.py leads      # Xem kết quả
```

## 📋 CLI Commands

```
python main.py init       Khởi tạo database
python main.py crawl      Cào dữ liệu FB Groups
python main.py classify   AI phân tích intent
python main.py run        Crawl + Classify 1 lần
python main.py loop       Chạy liên tục 24/7
python main.py stats      Xem thống kê
python main.py leads      Xem top leads
python main.py outreach   Xem trước tin nhắn
python main.py send       Gửi tin qua BizClaw
python main.py bizclaw    Kiểm tra BizClaw status
```

## 🧪 Tests

```bash
python test_all.py    # 19 test cases
```

## 🔧 Cấu hình FB Cookies

```bash
# 1. Cài extension "Get cookies.txt LOCALLY" trên Chrome
# 2. Login Facebook → Click extension → Export
# 3. Lưu file vào: data/fb_cookies.txt
```

## 📊 Intent Classification

Agent 2 phân loại comment thành 5 loại:

| Intent | Mô tả | Score |
|:---|:---|:---|
| `JOIN_TEAM` | Muốn tham gia, hợp tác | 70-100 |
| `ASK_QUESTION` | Hỏi về kỹ năng, công cụ | 50-80 |
| `SHARE_PAIN` | Chia sẻ khó khăn thực tế | 60-90 |
| `OFFER_HELP` | Đề nghị giúp đỡ | 40-70 |
| `NOISE` | Reaction đơn thuần | 0-30 |

## 📁 Project Structure

```
social-lead-gen/
├── main.py                   # Orchestrator CLI
├── database/
│   ├── schema.sql            # SQLite DDL
│   └── db.py                 # CRUD operations
├── agent_1_crawler/
│   ├── config.py             # Groups & keywords
│   ├── scraper.py            # facebook-scraper wrapper
│   └── avatar_checker.py     # Avatar hash check
├── agent_2_classifier/
│   ├── prompts.py            # Prompt templates
│   └── classifier.py         # OpenRouter + scoring
├── agent_3_bizclaw/
│   └── connector.py          # BizClaw Gateway API
├── test_all.py               # Test suite
├── start_bizclaw.bat         # Quick start BizClaw
└── run_pipeline.bat          # One-click pipeline
```

## 📜 License

MIT
