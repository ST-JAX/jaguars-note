#!/usr/bin/env python3
# combine_scraper.py

import os
import json
import csv
import time
from bs4 import BeautifulSoup, Comment

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

ID_FILE = "pfr_ids.json"


def load_id_map():
    if os.path.exists(ID_FILE):
        return json.load(open(ID_FILE, "r", encoding="utf-8"))
    return {}


def save_id_map(m):
    json.dump(m, open(ID_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def resolve_player_id(name, id_map):
    pid = id_map.get(name)
    if pid:
        return pid
    new = input(f"{name} の PFR ID が未登録です。IDを入力、空Enterでスキップ: ")
    if new:
        id_map[name] = new
        save_id_map(id_map)
        return new
    return None


def fetch_player_soup(player_id):
    url = f"https://www.pro-football-reference.com/players/{player_id[0]}/{player_id}.htm"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280x800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        time.sleep(3)
        html = driver.page_source
        return BeautifulSoup(html, "html.parser")
    finally:
        driver.quit()


def summary_combine(soup, year=None):
    # 1) コメントノードをすべて取得
    comments = soup.find_all(string=lambda t: isinstance(t, Comment))

    # 2) コメントの中から「id="combine"」を含むものを探す
    combine_tbl = None
    for comment in comments:
        if 'id="combine"' in comment:
            inner = BeautifulSoup(comment, "html.parser")
            combine_tbl = inner.find("table", id="combine")
            break

    # 3) テーブル自体が見つからない場合は全項目 "-" を返す
    if not combine_tbl:
        return "40yd: - / " "Bench: - / " "VJ: - / " "BJ: - / " "Shuttle: - / " "3Cone: -"

    # 4) tbody の一行目を取得
    tr = combine_tbl.find("tbody").find("tr")

    # 5) 各セルを取り出し、空文字なら "-" を返すヘルパー
    def get_cell_or_dash(stat):
        td = tr.find(attrs={"data-stat": stat})
        text = td.get_text(strip=True) if td else ""
        return text if text else "-"

    # 6) フォーマットに当てはめて返す
    return (
        f"40yd: {get_cell_or_dash('forty_yd')} / "
        f"Bench: {get_cell_or_dash('bench_reps')} / "
        f"VJ: {get_cell_or_dash('vertical')} / "
        f"BJ: {get_cell_or_dash('broad_jump')} / "
        f"Shuttle: {get_cell_or_dash('shuttle')} / "
        f"3Cone: {get_cell_or_dash('cone')}"
    )


# カテゴリマップ
CATEGORY_FUNCS = {
    "combine": summary_combine,
}


def process_csv():
    id_map = load_id_map()
    with open("players.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            name = rec["name"]
            pid = resolve_player_id(name, id_map)
            if not pid:
                print(f"[skip] {name}")
                continue

            print(f"\n{name}")
            try:
                soup = fetch_player_soup(pid)
            except Exception as e:
                print(f"[error] {e}")
                continue

            print("Stats (Combine)")
            print(CATEGORY_FUNCS["combine"](soup, None))  # ← 2個渡してOK


if __name__ == "__main__":
    process_csv()
