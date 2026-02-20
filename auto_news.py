import os
import requests
import datetime
import hashlib
import base64
import random
from xml.sax.saxutils import escape

# ==========================================
# 1. 設定情報（GitHub Secretsから取得）
# ==========================================
def get_env(key):
    val = os.getenv(key)
    return val.strip() if val else None

NOTION_TOKEN = get_env("NOTION_TOKEN")
NOTION_NEWS_DB_ID = get_env("NOTION_NEWS_DB_ID")
HATENA_USER = get_env("HATENA_USER")
HATENA_BLOG = get_env("HATENA_BLOG")
HATENA_API_KEY = get_env("HATENA_API_KEY")
# アーカイブ用（2025一覧）とバー専用（最新10件）の2つのID
HATENA_NEWS_PAGE_ID = get_env("HATENA_NEWS_PAGE_ID")
HATENA_LATEST_NEWS_PAGE_ID = get_env("HATENA_LATEST_NEWS_PAGE_ID")

# アーカイブ対象のシーズン
TARGET_SEASON = 2025

# NotionのType名とCSSクラスの変換マップ
TYPE_MAP = {
    "Contract": "contract",
    "Draft": "draft",
    "FA": "fa",
    "Injury": "injury",
    "News": "news",
    "Roster Move": "roster-move",
    "Trade": "trade",
    "Coaching": "coaching",
    "Awards": "awards"
}

def fetch_news_from_notion(season_filter=None, page_size=100):
    """Notionからニュースを取得。season_filterがあればその年のみ、なければ全期間"""
    url = f"https://api.notion.com/v1/databases/{NOTION_NEWS_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # 基本のクエリ（日付順）
    payload = {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": page_size
    }
    
    # シーズン指定（数値型）がある場合はフィルターを追加
    if season_filter:
        payload["filter"] = {
            "property": "Season",
            "number": {"equals": int(season_filter)}
        }
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code != 200:
        print(f"Notion Error: {res.text}")
        res.raise_for_status()
        
    data = res.json()
    news_list = []
    for page in data["results"]:
        props = page["properties"]

        # Formatted News（Formula）から取得
        formula_obj = props.get("Formatted News", {}).get("formula", {})
        title = formula_obj.get("string") if formula_obj.get("string") else "No Title"
        
        # 日付取得
        date_obj = props.get("Date", {}).get("date")
        date = date_obj["start"] if date_obj else "2025-01-01"
        
        # タイプ取得
        type_obj = props.get("Type", {}).get("select")
        ntype = type_obj["name"] if type_obj else "News"
        
        # URL取得
        url_obj = props.get("URL")
        url_val = url_obj.get("url") if url_obj else None
        
        news_list.append({
            "date": date.replace("-", "/"),
            "title": title,
            "type": ntype,
            "url": url_val
        })
    return news_list

def generate_full_page_html(news_data):
    """アーカイブページ（フィルタ機能付き）のHTMLを生成"""
    items_html = ""
    for item in news_data:
        css_type = TYPE_MAP.get(item["type"], "news")
        title_part = f'<a href="{item["url"]}" class="news-item-title">{escape(item["title"])}</a>' if item["url"] else f'<span class="news-item-title">{escape(item["title"])}</span>'
        
        items_html += f'''
<li class="news-item" data-type="{css_type}">
    <span class="news-item-date">{item["date"]}</span>
    <span class="news-item-type-col"><span class="news-item-type news-item-type--{css_type}">{item["type"]}</span></span>
    {title_part}
</li>'''

    return f'''
<div class="news-list-wrapper">
    <div class="news-filter-bar">
        <button class="news-filter-btn is-active" data-filter="all">All</button> 
        <button class="news-filter-btn" data-filter="contract">Contract</button> 
        <button class="news-filter-btn" data-filter="draft">Draft</button> 
        <button class="news-filter-btn" data-filter="fa">FA</button> 
        <button class="news-filter-btn" data-filter="injury">Injury</button> 
        <button class="news-filter-btn" data-filter="news">News</button> 
        <button class="news-filter-btn" data-filter="roster-move">Roster Move</button> 
        <button class="news-filter-btn" data-filter="trade">Trade</button>
        <button class="news-filter-btn" data-filter="coaching">Coaching</button>
        <button class="news-filter-btn" data-filter="awards">Awards</button>
    </div>
    <ul class="news-list js-news-list">
        {items_html}
    </ul>
</div>

<script>
document.addEventListener("DOMContentLoaded", function () {{
    const list = document.querySelector(".js-news-list");
    if (!list) return;
    const items = Array.from(list.querySelectorAll(".news-item"));
    const buttons = Array.from(document.querySelectorAll(".news-filter-btn"));

    buttons.forEach((btn) => {{
        btn.addEventListener("click", () => {{
            const filter = btn.dataset.filter;
            buttons.forEach((b) => b.classList.remove("is-active"));
            btn.classList.add("is-active");

            items.forEach((item) => {{
                const t = item.dataset.type;
                if (filter === "all" || filter === t) {{
                    item.style.display = "";
                }} else {{
                    item.style.display = "none";
                }}
            }});
        }});
    }});
}});
</script>
'''

def generate_bar_snippet_html(news_data):
    """ニュースバーが読み込むための、純粋なリストのみのHTMLを生成"""
    items_html = ""
    for item in news_data:
        css_type = TYPE_MAP.get(item["type"], "news")
        title_part = f'<a href="{item["url"]}" class="news-item-title">{escape(item["title"])}</a>' if item["url"] else f'<span class="news-item-title">{escape(item["title"])}</span>'
        
        items_html += f'''
<li class="news-item" data-type="{css_type}">
    <span class="news-item-date">{item["date"]}</span>
    <span class="news-item-type-col"><span class="news-item-type news-item-type--{css_type}">{item["type"]}</span></span>
    {title_part}
</li>'''
    return f'<ul class="news-list js-news-list">{items_html}</ul>'

def update_hatena_page(page_id, title, html_content):
    """はてなブログの指定IDのページを更新"""
    url = f"https://blog.hatena.ne.jp/{HATENA_USER}/{HATENA_BLOG}/atom/page/{page_id}"
    
    created = datetime.datetime.now().isoformat() + "Z"
    nonce = hashlib.sha1(str(random.random()).encode()).digest()
    digest = hashlib.sha1(nonce + created.encode() + HATENA_API_KEY.encode()).digest()
    wsse = f'UsernameToken Username="{HATENA_USER}", PasswordDigest="{base64.b64encode(digest).decode()}", Nonce="{base64.b64encode(nonce).decode()}", Created="{created}"'
    
    xml_data = f'''<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
  <title>{title}</title>
  <content type="text/html">
    {escape(html_content)}
  </content>
</entry>'''

    headers = {"X-WSSE": wsse, "Content-Type": "application/xml"}
    res = requests.put(url, data=xml_data.encode('utf-8'), headers=headers)
    
    if res.status_code == 200:
        print(f"Successfully updated: {title}")
    else:
        print(f"Failed to update {title}. Status: {res.status_code}")
        print(res.text)

def main():
    # 1. アーカイブ用データ取得 (2025年全件)
    print(f"Fetching {TARGET_SEASON} News for Archive...")
    archive_news = fetch_news_from_notion(season_filter=TARGET_SEASON, page_size=100)
    archive_html = generate_full_page_html(archive_news)
    update_hatena_page(HATENA_NEWS_PAGE_ID, f"NEWS // {TARGET_SEASON}", archive_html)
    
    # 2. ニュースバー用データ取得 (全期間から最新10件)
    print("Fetching Global Latest News for Bar...")
    latest_news = fetch_news_from_notion(season_filter=None, page_size=10)
    bar_html = generate_bar_snippet_html(latest_news)
    update_hatena_page(HATENA_LATEST_NEWS_PAGE_ID, "LATEST_NEWS_BAR_DATA", bar_html)

if __name__ == "__main__":
    main()
