📋 **【貼り付けるコード（タップしてコピー）】**
```python
#!/usr/bin/env python3
import os
import time
import json
import re
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# 南口さんのDiscord Webhook URL
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1570755612592050256/yhuZMjrz1sJdhyhRgOxXYDTtBHhiAcIszVAmsnvjODyl7NZ8_ZdnozNZKHQA0Z4J4XXV"
)

# 監視対象（アメドリ通販部）
TARGET_URLS = [
    "https://www.amenitydream.com/phone/product-group/49",   # パック・BOX
    "https://www.amenitydream.com/phone/product-list/1265",  # ポケモンカード
]

# 監視キーワード
WATCH_KEYWORDS = [
    "30th", "ハドウシーカー", "ストームエメラルダ", "神の支配", 
    "ヒロインズ", "世界最強の戦士", "ワンピース", "スペシャルデッキセット",
    "メガオーダイル", "メガブレイブ", "メガシンフォニア", "テラスタルフェス",
    "box", "ブースター"
]

# 監視間隔（秒）
CHECK_INTERVAL_SECONDS = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

seen_in_stock_ids = set()
first_run = True

def send_discord_alert(product):
    payload = {
        "username": "アメドリ速報くん 🤖",
        "content": "@everyone 🚨 **【アメニティードリーム 入荷速報！】**",
        "embeds": [{
            "title": product["name"],
            "url": product["url"],
            "color": 15158332,
            "fields": [
                {"name": "💰 価格", "value": product.get("price", "不明"), "inline": True},
                {"name": "📦 在庫状況", "value": product.get("stock", "在庫あり"), "inline": True},
                {"name": "⚡ 購入リンク", "value": f"[商品ページへ直行]({product['url']})", "inline": False},
            ],
            "footer": {"text": "南口さん専用 監視Bot"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }]
    }
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[{time.strftime('%H:%M:%S')}] Discord通知送信: {product['name']}")
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def parse_page(html):
    products = []
    blocks = re.findall(r'<tr class="list_item_tr">(.*?)</tr>', html, re.DOTALL)
    for b in blocks:
        title_m = re.search(r'<h3 class="item_name"><a[^>]*>(.*?)</a></h3>', b, re.DOTALL)
        if not title_m:
            continue
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
        price_m = re.search(r'<span class="pricech">([^<]+)</span>', b)
        price = price_m.group(1).strip() if price_m else "不明"
        stock_m = re.search(r'<p class="stock">([^<]+)</p>', b)
        stock = stock_m.group(1).strip() if stock_m else "在庫あり"
        url_m = re.search(r'href="([^"]*product/(\d+))"', b)
        if not url_m:
            continue
        raw_url, pid = url_m.group(1), url_m.group(2)
        url = raw_url if raw_url.startswith("http") else f"https://www.amenitydream.com{raw_url}"
        is_in_stock = "在庫なし" not in stock
        products.append({
            "id": pid, "name": title, "url": url, "price": price,
            "stock": stock, "in_stock": is_in_stock
        })
    return products

def check_updates():
    global seen_in_stock_ids, first_run
    for target_url in TARGET_URLS:
        try:
            req = urllib.request.Request(target_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                products = parse_page(html)
                for p in products:
                    name_lower = p["name"].lower()
                    matches = any(kw.lower() in name_lower for kw in WATCH_KEYWORDS)
                    if matches and p["in_stock"]:
                        if p["id"] not in seen_in_stock_ids:
                            seen_in_stock_ids.add(p["id"])
                            if not first_run:
                                send_discord_alert(p)
                    elif not p["in_stock"]:
                        if p["id"] in seen_in_stock_ids:
                            seen_in_stock_ids.remove(p["id"])
        except Exception as e:
            print(f"チェックエラー: {e}")
    if first_run:
        first_run = False

def monitor_loop():
    while True:
        try:
            check_updates()
        except Exception as e:
            print(f"ループ例外: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Amenity Dream Watcher is running! OK\n")
    def log_message(self, format, *args): pass

if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()
```
