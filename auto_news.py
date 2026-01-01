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
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_NEWS_DB_ID = os.getenv("NOTION_NEWS_DB_ID")
HATENA_USER = os.getenv("HATENA_USER")
HATENA_BLOG = os.getenv("HATENA_BLOG")
HATENA_API_KEY = os.getenv("HATENA_API_KEY")
HATENA_NEWS_PAGE_ID = os.getenv("HATENA_NEWS_PAGE_ID")

# 現在の表示対象シーズン
TARGET_SEASON = "2025"

# Type名とCSSクラスの変換マップ
TYPE_MAP = {
    "Contract": "contract",
    "Draft": "draft",
    "FA": "fa",
    "Injury": "injury",
    "News": "news",
    "Roster Move": "roster-move",
    "Trade": "trade",
}


def fetch_news_from_notion():
    """Notionから指定シーズンのニュースを取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_NEWS_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    # フィルタ：SeasonプロパティがTARGET_SEASONと一致するもの
    # ソート：日付の新しい順
    payload = {
        "filter": {"property": "Season", "number": {"equals": int(TARGET_SEASON)}},
        "sorts": [{"property": "Date", "direction": "descending"}],
    }

    res = requests.post(url, headers=headers, json=payload)

    res.raise_for_status()
    data = res.json()

    news_list = []
    for page in data["results"]:
        props = page["properties"]

        # 各プロパティの安全な取得
        title_list = props.get("Title", {}).get("title", [])
        title = title_list[0]["text"]["content"] if title_list else "No Title"

        date_obj = props.get("Date", {}).get("date")
        date = date_obj["start"] if date_obj else "2025/01/01"

        type_obj = props.get("Type", {}).get("select")
        ntype = type_obj["name"] if type_obj else "News"

        url_obj = props.get("URL")
        url_val = url_obj.get("url") if url_obj else None

        news_list.append({"date": date.replace("-", "/"), "title": title, "type": ntype, "url": url_val})
    return news_list


def generate_news_html(news_data):
    """ニュース一覧のHTML全体を生成"""
    items_html = ""
    for item in news_data:
        css_type = TYPE_MAP.get(item["type"], "news")

        if item["url"]:
            title_part = f'<a href="{item["url"]}" class="news-item-title">{escape(item["title"])}</a>'
        else:
            title_part = f'<span class="news-item-title">{escape(item["title"])}</span>'

        # ここは変数を埋め込むので { } は1重でOK
        items_html += f"""
<li class="news-item" data-type="{css_type}">
    <span class="news-item-date">{item["date"]}</span>
    <span class="news-item-type-col"><span class="news-item-type news-item-type--{css_type}">{item["type"]}</span></span>
    {title_part}
</li>"""

    # 【重要】JSを含む全体構造。JSの波括弧は {{ }} にしているよ！
    full_html = f"""
<div class="news-list-wrapper">
    <header class="news-list-header">
        <h2 class="news-list-title">NEWS {TARGET_SEASON}</h2>
        <p class="news-list-sub">{TARGET_SEASON}シーズンのJAX関連ニュース一覧</p>
    </header>
    <div class="news-filter-bar">
        <button class="news-filter-btn is-active" data-filter="all">All</button> 
        <button class="news-filter-btn" data-filter="contract">Contract</button> 
        <button class="news-filter-btn" data-filter="draft">Draft</button> 
        <button class="news-filter-btn" data-filter="fa">FA</button> 
        <button class="news-filter-btn" data-filter="injury">Injury</button> 
        <button class="news-filter-btn" data-filter="news">News</button> 
        <button class="news-filter-btn" data-filter="roster-move">Roster Move</button> 
        <button class="news-filter-btn" data-filter="trade">Trade</button>
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

            // ボタンの活性化切り替え
            buttons.forEach((b) => b.classList.remove("is-active"));
            btn.classList.add("is-active");

            // フィルタリング実行
            items.forEach((item) => {{
                const t = item.dataset.type;
                // 表示・非表示の切り替え
                if (filter === "all" || filter === t) {{
                    item.style.display = ""; // 表示
                }} else {{
                    item.style.display = "none"; // 非表示
                }}
            }});
        }});
    }});
}});
</script>
"""
    return full_html


def update_hatena_page(html_content):
    """はてなブログの固定ページを更新"""
    url = f"https://blog.hatena.ne.jp/{HATENA_USER}/{HATENA_BLOG}/atom/page/{HATENA_NEWS_PAGE_ID}"

    # WSSE認証の作成
    user_name = HATENA_USER
    api_key = HATENA_API_KEY
    created = datetime.datetime.now().isoformat() + "Z"
    nonce = hashlib.sha1(str(random.random()).encode()).digest()
    digest = hashlib.sha1(nonce + created.encode() + api_key.encode()).digest()

    wsse = f'UsernameToken Username="{user_name}", PasswordDigest="{base64.b64encode(digest).decode()}", Nonce="{base64.b64encode(nonce).decode()}", Created="{created}"'

    # AtomPub形式のXML
    xml_data = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
  <content type="text/html">
    {escape(html_content)}
  </content>
</entry>"""

    headers = {"X-WSSE": wsse, "Content-Type": "application/xml"}
    res = requests.put(url, data=xml_data.encode("utf-8"), headers=headers)

    if res.status_code == 200:
        print(f"Successfully updated News page!")
    else:
        print(f"Failed to update. Status: {res.status_code}")
        print(res.text)


def main():
    print("Fetching News from Notion...")
    news_data = fetch_news_from_notion()

    print(f"Generating HTML for {len(news_data)} items...")
    full_html = generate_news_html(news_data)

    print("Updating Hatena Blog...")
    update_hatena_page(full_html)

if __name__ == "__main__":
    main()
