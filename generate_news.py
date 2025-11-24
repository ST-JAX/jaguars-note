#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from datetime import date
import html
import pandas as pd

# Type → スラッグ（CSSクラスや data-type 用）
TYPE_SLUG_MAP = {
    "Contract": "contract",
    "Draft": "draft",
    "FA": "fa",
    "Injury": "injury",
    "News": "news",
    "Roster Move": "roster-move",
    "Trade": "trade",
}


def season_year_from_date(d: date) -> int:
    """
    3月〜翌年2月で1シーズンとみなす。
    例: 2025/03/01〜2026/02/28 → season_year = 2025
    """
    return d.year if d.month >= 3 else d.year - 1


def load_news_df(csv_path: str) -> pd.DataFrame:
    """
    CSVを読み込んで共通の列名に整形。
    必要な列: Date, Title, Type, URL
    """
    df = pd.read_csv(csv_path)

    required = ["Date", "Title", "Type", "URL"]
    for col in required:
        if col not in df.columns:
            raise SystemExit(f"CSVに必要な列 {col} が見つかりません")

    df = df[required].copy()
    df.rename(columns={"Date": "date_raw", "Title": "title", "Type": "type", "URL": "url"}, inplace=True)

    # Date列を日付型に変換（時間が付いていてもOK）
    df["date"] = pd.to_datetime(df["date_raw"], errors="coerce").dt.date
    if df["date"].isna().any():
        bad_rows = df[df["date"].isna()]
        raise SystemExit(f"日付が解釈できない行があります: \n{bad_rows[['date_raw','title']]}")

    # シーズン年を計算
    df["season_year"] = df["date"].apply(season_year_from_date)

    # Type整形
    df["type"] = df["type"].astype(str).str.strip()

    return df


def type_to_slug(t: str) -> str:
    t = t.strip()
    return TYPE_SLUG_MAP.get(t, t.lower().replace(" ", "-"))


def escape(s: str) -> str:
    return html.escape(str(s), quote=True)


def format_md_date(d: date) -> str:
    """ニュースバー用: 11/18 形式"""
    return f"{d.month}/{d.day}"


def format_ymd_date(d: date) -> str:
    """一覧用: 2025/11/18 形式"""
    return d.strftime("%Y/%m/%d")


def generate_newsbar_items(df: pd.DataFrame, limit: int = 10) -> str:
    """
    最新limit件のニュースバー用 <li>... を生成
    """
    df_sorted = df.sort_values("date", ascending=False).head(limit)

    lis = []
    for _, row in df_sorted.iterrows():
        d = row["date"]
        date_str = format_md_date(d)
        title = escape(row["title"])
        url = str(row.get("url") or "").strip()

        type_name = row["type"]
        type_slug = type_to_slug(type_name)
        type_class = f"newsbar-b-type--{type_slug}"

        if url:
            title_html = f'<a href="{escape(url)}" class="newsbar-b-title">{title}</a>'
        else:
            title_html = f'<span class="newsbar-b-title">{title}</span>'

        li = (
            '        <li class="newsbar-b-item">\n'
            f'          <span class="newsbar-b-date">{date_str}</span>\n'
            f'          <span class="newsbar-b-type {type_class}">{escape(type_name)}</span>\n'
            f"          {title_html}\n"
            "        </li>"
        )
        lis.append(li)

    return "\n".join(lis)


def generate_newslist_items(df: pd.DataFrame, season_year: int) -> str:
    """
    指定シーズン年のニュース一覧 <li>... を生成
    """
    one = df[df["season_year"] == season_year].copy()
    if one.empty:
        return ""

    one = one.sort_values("date", ascending=False)

    lis = []
    for _, row in one.iterrows():
        d = row["date"]
        date_str = format_ymd_date(d)
        title = escape(row["title"])
        url = str(row.get("url") or "").strip()

        type_name = row["type"]
        type_slug = type_to_slug(type_name)
        type_class = f"news-item-type--{type_slug}"
        data_type = type_slug

        if url:
            title_html = f'<a href="{escape(url)}" class="news-item-title">{title}</a>'
        else:
            title_html = f'<span class="news-item-title">{title}</span>'

        li = (
            f'    <li class="news-item" data-type="{data_type}">\n'
            f'      <span class="news-item-date">{date_str}</span>\n'
            f'      <span class="news-item-type-col">'
            f'<span class="news-item-type {type_class}">{escape(type_name)}</span>'
            f"</span>\n"
            f"      {title_html}\n"
            f"    </li>"
        )
        lis.append(li)

    return "\n".join(lis)


def main():
    if len(sys.argv) < 2:
        print("使い方: generate_news.py DB_News.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    base_dir = os.path.dirname(os.path.abspath(csv_path))

    print(f"[INFO] CSV 読み込み: {csv_path}")

    df = load_news_df(csv_path)

    # CSV内の「一番新しい日付」からシーズン年を決定
    latest_date = df["date"].max()
    season_year = season_year_from_date(latest_date)
    print(f"[INFO] 最新日付: {latest_date} → season_year = {season_year}")

    newsbar_output = os.path.join(base_dir, "newsbar.html")
    newslist_output = os.path.join(base_dir, f"newslist_{season_year}.html")

    newsbar_html = generate_newsbar_items(df, limit=10)
    newslist_html = generate_newslist_items(df, season_year)

    Path(newsbar_output).write_text(newsbar_html, encoding="utf-8")
    Path(newslist_output).write_text(newslist_html, encoding="utf-8")

    print(f"[INFO] ニュースバーHTML 出力: {newsbar_output}")
    print(f"[INFO] ニュース一覧HTML 出力: {newslist_output}")


if __name__ == "__main__":
    main()
