#!/usr/bin/env python3
import os
import time
import json
import re
import html
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1570755612592050256/yhuZMjrz1sJdhyhRgOxXYDTtBHhiAcIszVAmsnvjODyl7NZ8_ZdnozNZKHQA0Z4J4XXV"
)

WATCH_KEYWORDS = [
    "ハドウシーカー", "ストームエメラルダ", "ムニキスゼロ", "ニンジャスピナー",
    "30th", "セレブレーション", "メガブレイブ", "メガシンフォニア", "テラスタルフェス",
    "アビスアイ", "メガドリーム", "インフェルノ",
    "神の支配", "east blue", "イーストブルー", "ヒロインズ", "世界最強の戦士",
]

CHECK_INTERVAL_SECONDS = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9",
}

seen_in_stock_ids = set()
first_run = True


def post_discord(payload):
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Discord送信エラー: {e}")


def send_discord_alert(product):
    shop_name = product.get("shop", "通販サイト")
    if "アメドリ" in shop_name or "アメニティ" in shop_name:
        embed_color = 15158332
    elif "カードラボ" in shop_name:
        embed_color = 3447003
    else:
        embed_color = 16753920
    payload = {
        "username": f"{shop_name} 速報くん 🤖",
        "content": f"@everyone 🚨 **【{shop_name} 入荷速報！】**",
        "embeds": [{
            "title": product["name"],
            "url": product["url"],
            "color": embed_color,
            "fields": [
                {"name": "🏪 ショップ", "value": shop_name, "inline": True},
                {"name": "💰 価格", "value": product.get("price", "定価/通常"), "inline": True},
                {"name": "📦 在庫状況", "value": product.get("stock", "在庫あり"), "inline": True},
                {"name": "⚡ 購入リンク", "value": f"[商品ページへ直行]({product['url']})", "inline": False},
            ],
            "footer": {"text": "アメドリ＆ホビステ＆カードラボ監視Bot (南口さん専用)"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }],
    }
    post_discord(payload)


def matches_target(name):
    nl = name.lower()
    if any(x in nl for x in ["サプライ", "スリーブ", "デッキケース", "プレイマット", "ロングカードボックス", "太陽神の支配", "スタートデッキ", "スペシャルデッキセット"]):
        return False
    if any(kw.lower() in nl for kw in WATCH_KEYWORDS):
        return True
    if ("ポケモン" in nl or "ポケカ" in nl) and ("box" in nl or "拡張パック" in nl):
        return True
    if ("ワンピース" in nl or "one piece" in nl) and ("box" in nl or "ブースター" in nl):
        return True
    return False


AMENITY_URLS = [
    "https://www.amenitydream.com/product-group/49",
    "https://www.amenitydream.com/product-list/1265",
    "https://www.amenitydream.com/product-list/4894",
    "https://www.amenitydream.com/product-list?keyword=30th",
    "https://www.amenitydream.com/product-list?keyword=%E3%83%8F%E3%83%89%E3%82%A6%E3%82%B7%E3%83%BC%E3%82%AB%E3%83%BC",
    "https://www.amenitydream.com/product-list?keyword=%E7%A5%9E%E3%81%AE%E6%94%AF%E9%85%8D",
]


def check_amenity_dream():
    products = []
    seen_ids = set()
    for target_url in AMENITY_URLS:
        try:
            req = urllib.request.Request(target_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                if "アクセスが集中" in raw:
                    continue
                blocks = re.findall(r'<li[^>]*class="[^"]*list_item[^"]*"[^>]*>(.*?)</li>', raw, re.DOTALL)
                for b in blocks:
                    name_m = re.search(r'class="goods_name"[^>]*>(.*?)</', b, re.DOTALL)
                    url_m = re.search(r'href="([^"]*product/(\d+))"', b)
                    if not name_m or not url_m:
                        continue
                    pid = f"ad_{url_m.group(2)}"
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    title = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
                    price_m = re.search(r'([\d,]+円)', b)
                    stock_m = re.search(r'(在庫数\s*\d+[点個]|在庫なし)', b)
                    stock = stock_m.group(1) if stock_m else "在庫なし"
                    is_in_stock = "在庫数" in stock
                    raw_url = url_m.group(1)
                    url = raw_url if raw_url.startswith("http") else f"https://www.amenitydream.com{raw_url}"
                    products.append({
                        "id": pid,
                        "shop": "アメニティードリーム",
                        "name": title,
                        "url": url,
                        "price": price_m.group(1) if price_m else "不明",
                        "stock": stock,
                        "in_stock": is_in_stock,
                    })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] アメドリ取得エラー ({target_url}): {e}")
    return products


CLABO_DIRECT_URLS = [
    ("408347", "ポケモンカードゲーム 30th CELEBRATION BOX"),
    ("420308", "ポケモンカードゲーム ハドウシーカー BOX"),
    ("395733", "ポケモンカードゲーム ストームエメラルダ BOX"),
    ("422274", "ONE PIECEカードゲーム EAST BLUE BOX"),
]

CLABO_SEARCH_QUERIES = ["30th CELEBRATION", "ハドウシーカー", "EAST BLUE", "神の支配"]


def check_clabo():
    products = []
    seen_ids = set()
    for code, fallback_name in CLABO_DIRECT_URLS:
        url = f"https://www.c-labo-online.jp/product/{code}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                title_m = re.search(r'<h1[^>]*>(.*?)</h1>', raw, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else fallback_name
                is_in_stock = ("カートに入れる" in raw) and ("在庫なし" not in raw)
                price_m = re.search(r'販売価格[^0-9]*([\d,]+円)', raw)
                seen_ids.add(f"cl_{code}")
                products.append({
                    "id": f"cl_{code}",
                    "shop": "カードラボ通販",
                    "name": title,
                    "url": url,
                    "price": price_m.group(1) if price_m else "会員価格",
                    "stock": "在庫あり" if is_in_stock else "在庫なし",
                    "in_stock": is_in_stock,
                })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] カードラボ直ページエラー ({code}): {e}")

    for q in CLABO_SEARCH_QUERIES:
        url = f"https://www.c-labo-online.jp/product-list?keyword={urllib.parse.quote(q)}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                blocks = re.findall(r'<li[^>]*class="[^"]*list_item[^"]*"[^>]*>(.*?)</li>', raw, re.DOTALL)
                for b in blocks:
                    name_m = re.search(r'class="goods_name"[^>]*>(.*?)</', b, re.DOTALL)
                    url_m = re.search(r'href="([^"]*product/(\d+))"', b)
                    if not name_m or not url_m:
                        continue
                    pid = f"cl_{url_m.group(2)}"
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    title = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
                    is_in_stock = ("カートに入れる" in b) and ("在庫なし" not in b)
                    raw_url = url_m.group(1)
                    purl = raw_url if raw_url.startswith("http") else f"https://www.c-labo-online.jp{raw_url}"
                    products.append({
                        "id": pid,
                        "shop": "カードラボ通販",
                        "name": title,
                        "url": purl,
                        "price": "会員価格",
                        "stock": "在庫あり" if is_in_stock else "在庫なし",
                        "in_stock": is_in_stock,
                    })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] カードラボ検索エラー ({q}): {e}")
    return products


HOBISTORE_QUERIES = [
    "ハドウシーカー", "ストームエメラルダ", "ムニキスゼロ", "ニンジャスピナー",
    "30th", "神の支配", "EAST BLUE", "ポケモンカード BOX", "ワンピース BOX",
]


def check_hobistore_yahoo():
    products = []
    target_urls = ["https://store.shopping.yahoo.co.jp/hbst-store/cdbdccf3be.html"]
    for q in HOBISTORE_QUERIES:
        target_urls.append(f"https://store.shopping.yahoo.co.jp/hbst-store/search.html?p={urllib.parse.quote(q)}")
    seen_codes = set()
    for target_url in target_urls:
        try:
            req = urllib.request.Request(target_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                for m in re.finditer(r'tname:(.*?);itemcode:(\d+);', raw):
                    code = m.group(2)
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    name = html.unescape(m.group(1)).strip()
                    products.append({
                        "id": f"hb_{code}",
                        "shop": "ホビステYahoo店",
                        "name": name,
                        "url": f"https://store.shopping.yahoo.co.jp/hbst-store/{code}.html",
                        "price": "定価/販売中",
                        "stock": "出品検知",
                        "in_stock": True,
                    })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ホビステ取得エラー: {e}")
    return products


def check_updates():
    global seen_in_stock_ids, first_run
    all_products = []
    all_products.extend(check_amenity_dream())
    all_products.extend(check_clabo())
    all_products.extend(check_hobistore_yahoo())
    for p in all_products:
        if matches_target(p["name"]) and p["in_stock"]:
            if p["id"] not in seen_in_stock_ids:
                seen_in_stock_ids.add(p["id"])
                if not first_run:
                    send_discord_alert(p)
        elif not p["in_stock"]:
            seen_in_stock_ids.discard(p["id"])
    if first_run:
        first_run = False
        post_discord({
            "username": "監視Bot ステータス 🟢",
            "content": f"🟢 **監視Bot（アメドリ検索強化＋カードラボ＋ホビステ）起動しました！**（取得商品数: {len(all_products)}件 / 15秒ごとに監視中）",
        })


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
        self.wfile.write(b"Amenity & C-labo & Hobi-ste Watcher is running! Status: OK\n")

    def log_message(self, format, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    run_server()
