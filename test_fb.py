"""Fix test: target [data-ad-comet-preview=message] trực tiếp."""
from playwright.sync_api import sync_playwright
import json, time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="vi-VN",
    )

    with open("data/fb_cookies.json") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)

    page = context.new_page()
    page.goto("https://www.facebook.com/groups/StartupVietnam/", wait_until="domcontentloaded", timeout=30000)
    
    # Chờ FB render xong — scroll chậm từng viewport
    print("Waiting 8s for initial load...")
    time.sleep(8)

    for i in range(5):
        page.evaluate(f"window.scrollTo(0, {(i+1) * 400})")
        time.sleep(2)

    # APPROACH: Lấy trực tiếp [data-ad-comet-preview="message"]
    posts = page.evaluate("""
    () => {
        // Tìm tất cả message containers 
        const msgs = document.querySelectorAll('[data-ad-comet-preview="message"]');
        const results = [];
        
        msgs.forEach((msgEl, i) => {
            const text = msgEl.innerText.trim();
            if (text.length < 3) return;
            
            // Walk up DOM để tìm post container (role=feed > div)
            let container = msgEl;
            for (let j = 0; j < 20; j++) {
                if (!container.parentElement) break;
                container = container.parentElement;
                if (container.getAttribute('role') === 'feed') break;
            }
            
            // Tìm author (strong hoặc h3/h4 link)
            const authorEl = container.querySelector('h3 a, h4 a, strong a, a[role="link"] strong');
            const authorName = authorEl ? authorEl.innerText.trim() : '';
            
            // Tìm post URL
            const linkEls = container.querySelectorAll('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]');
            const postUrl = linkEls.length > 0 ? linkEls[0].href : '';
            
            results.push({
                index: i,
                text: text.substring(0, 300),
                author: authorName,
                url: postUrl.substring(0, 100),
            });
        });
        
        return results;
    }
    """)

    print(f"\nFound {len(posts)} posts via message selector:")
    for item in posts:
        print(f"\n  Post {item['index']}:")
        print(f"    Author: {item['author']}")
        print(f"    Text: {item['text'][:150]}")
        print(f"    URL: {item['url']}")

    # ALSO: try feed children approach
    print("\n--- Feed children with text ---")
    feed_posts = page.evaluate("""
    () => {
        const feed = document.querySelector('[role="feed"]');
        if (!feed) return [];
        
        const results = [];
        for (let i = 0; i < feed.children.length; i++) {
            const child = feed.children[i];
            const text = child.innerText.trim();
            const clean = text.replace(/Facebook\\n?/g, '').replace(/\\n+/g, ' ').trim();
            if (clean.length > 30) {
                results.push({
                    index: i,
                    text_length: clean.length,
                    preview: clean.substring(0, 150),
                });
            }
        }
        return results;
    }
    """)
    
    for item in feed_posts[:5]:
        print(f"  Feed[{item['index']}] ({item['text_length']} chars): {item['preview'][:100]}")

    browser.close()
