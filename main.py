#!/usr/bin/env python3
"""
アメドリ ＆ ホビステYahoo店 入荷・再販監視Bot (for South-guchi san)
Developed with Hana 🌸
"""

import os
import time
import json
import re
import html
import threading
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= 設定エリア =================
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1570755612592050256/yhuZMjrz1sJdhyhRgOxXYDTtBHhiAcIszVAmsnvjODyl7NZ8_ZdnozNZKHQA0Z4J4XXV"
)

# 監視キーワード（11月中旬・下旬再販 ＆ 12月祭り ＆ ワンピ新弾）
WATCH_KEYWORDS = [
    # ポケカ 11月再販＆新弾本命
    "ハドウシーカー",
    "ストームエメラルダ",
    "ムニキスゼロ",
    "ニンジャスピナー",
    "30th",
    "セレブレーション",
    "スペシャルデッキセット",
    "メガオーダイル",
    "メガブレイブ",
    "メガシンフォニア",
    "テラスタルフェス",
    # ポケカ 12月予想枠
    "アビスアイ",
    "メガドリーム",
    "インフェルノ",
    # ワンピース 新弾＆本命
    "神の支配",
    "east blue",
    "イーストブルー",
    "ワンピース",
    "one piece",
    "ヒロインズ",
    "世界最強の戦士",
]

# チェック間隔（秒）
CHECK_INTERVAL_SECONDS = 15

# ============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9",
}

seen_in_stock_ids = set()
first_run = True


def send_discord_alert(product):
    shop_name = product.get("shop", "通販サイト")
    embed_color = 15158332 if "アメドリ" in shop_name else 16753920  # アメドリ=赤, ホビステ=オレンジ

    payload = {
        "username": f"{shop_name} 速報くん 🤖",
        "avatar_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4e2.png",
        "content": f"@everyone 🚨 **【{shop_name} 入荷速報！】**",
        "embeds": [
            {
                "title": product["name"],
                "url": product["url"],
                "color": embed_color,
                "fields": [
                    {"name": "🏪 ショップ", "value": shop_name, "inline": True},
                    {"name": "💰 価格", "value": product.get("price", "定価/通常"), "inline": True},
                    {"name": "📦 在庫状況", "value": product.get("stock", "在庫あり"), "inline": True},
                    {"name": "⚡ 購入リンク", "value": f"[商品ページへ直行]({product['url']})", "inline": False},
                ],
                "footer": {"text": "アメドリ＆ホビステ監視Bot (南口さん専用)"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
    }

    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[{time.strftime('%H:%M:%S')}] Discord通知送信成功 ({shop_name}): {product['name']}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Discord送信エラー: {e}")


# --- 1. アメニティードリーム通販部の監視 ---
AMENITY_URLS = [
    "https://www.amenitydream.com/phone/product-group/49",  # パック・BOX
    "https://www.amenitydream.com/phone/product-list/1265",  # ポケモンカード
]

def check_amenity_dream():
    products = []
    for target_url in AMENITY_URLS:
        try:
            req = urllib.request.Request(target_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                blocks = re.findall(r'<tr class="list_item_tr">(.*?)</tr>', raw, re.DOTALL)
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
                    raw_url = url_m.group(1)
                    pid = f"ad_{url_m.group(2)}"
                    url = raw_url if raw_url.startswith("http") else f"https://www.amenitydream.com{raw_url}"

                    is_in_stock = "在庫なし" not in stock

                    products.append({
                        "id": pid,
                        "shop": "アメニティードリーム",
                        "name": title,
                        "url": url,
                        "price": price,
                        "stock": stock,
                        "in_stock": is_in_stock,
                    })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] アメドリ取得エラー ({target_url}): {e}")
    return products


# --- 2. ホビーステーション Yahoo!店の監視 ---
HOBISTORE_QUERIES = [
    "ハドウシーカー",
    "ストームエメラルダ",
    "ムニキスゼロ",
    "ニンジャスピナー",
    "神の支配",
    "EAST BLUE",
    "ポケモンカード BOX",
    "ワンピース BOX",
]

def check_hobistore_yahoo():
    products = []
    # 予約一覧ページ
    target_urls = ["https://store.shopping.yahoo.co.jp/hbst-store/cdbdccf3be.html"]
    # キーワード検索ページ
    for q in HOBISTORE_QUERIES:
        enc_q = urllib.parse.quote(q)
        target_urls.append(f"https://store.shopping.yahoo.co.jp/hbst-store/search.html?p={enc_q}")

    seen_codes = set()
    for target_url in target_urls:
        try:
            req = urllib.request.Request(target_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                for m in re.finditer(r'tname:(.*?);itemcode:(\d+);', raw):
                    code = m.group(2)
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    name = html.unescape(m.group(1)).strip()
                    url = f"https://store.shopping.yahoo.co.jp/hbst-store/{code}.html"

                    products.append({
                        "id": f"hb_{code}",
                        "shop": "ホビステYahoo店",
                        "name": name,
                        "url": url,
                        "price": "定価/販売中",
                        "stock": "出品検知",
                        "in_stock": True,
                    })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ホビステ取得エラー: {e}")
    return products


def check_updates():
    global seen_in_stock_ids, first_run
    print(f"[{time.strftime('%H:%M:%S')}] チェック実行中（アメドリ ＆ ホビステYahoo店）...")

    all_products = []
    all_products.extend(check_amenity_dream())
    all_products.extend(check_hobistore_yahoo())

    for p in all_products:
        name_lower = p["name"].lower()
        matches_keyword = any(kw.lower() in name_lower for kw in WATCH_KEYWORDS)

        if matches_keyword and p["in_stock"]:
            if p["id"] not in seen_in_stock_ids:
                seen_in_stock_ids.add(p["id"])
                if not first_run:
                    print(f"🔥 新入荷検知 [{p['shop']}]: {p['name']} ({p.get('price')})")
                    send_discord_alert(p)
                else:
                    print(f"初期ロード [{p['shop']}]: {p['name']}")
        elif not p["in_stock"]:
            if p["id"] in seen_in_stock_ids:
                seen_in_stock_ids.remove(p["id"])

    if first_run:
        first_run = False
        print(f"[{time.strftime('%H:%M:%S')}] 初期読み込み完了（アメドリ＆ホビステ 24時間監視稼働中...）")


def monitor_loop():
    while True:
        try:
            check_updates()
        except Exception as e:
            print(f"ループ内例外: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Amenity & Hobi-ste Watcher is running! Status: OK\n")

    def log_message(self, format, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health Server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    run_server()
