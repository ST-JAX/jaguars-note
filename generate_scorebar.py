
import pandas as pd
import sys
import os
from datetime import datetime

# ==== 入力チェック ====
if len(sys.argv) < 2:
    print("[使い方] generate_scorebar.py [試合CSVファイル]")
    sys.exit(1)

csv_path = sys.argv[1]
script_dir = os.path.dirname(os.path.abspath(__file__))
color_path = os.path.join(script_dir, "team_color.xlsx")

# ==== データ読み込み ====
schedule_df = pd.read_csv(csv_path, dtype=str)
colors_df = pd.read_excel(color_path)

# ==== カラム整形 ====
schedule_df.columns = [col.strip() for col in schedule_df.columns]
schedule_df = schedule_df.rename(columns={
    "試合日時（日本時間）": "datetime",
    "Week": "week",
    "チーム": "opponent",
    "Home/Away": "home",
    "Score": "score",
    "Win/Lose": "win"
})

# ==== 日時整形 ====
datetime_clean = schedule_df["datetime"].fillna("").str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
parsed_dt = pd.to_datetime(datetime_clean, errors="coerce")
schedule_df["datetime"] = parsed_dt
schedule_df["datetime_str"] = datetime_clean

# ==== 勝敗・スコア処理 ====
schedule_df["result"] = schedule_df["win"].map({
    "Win": "W", "Lose": "L", "Draw": "D"
}).fillna("-")
schedule_df["score"] = schedule_df["score"].fillna("-")

# ==== venue 表示 ====
schedule_df["venue"] = schedule_df["home"].map({
    "Home": "Home", "Away": "Away"
}).fillna("")
schedule_df["venue_class"] = schedule_df["venue"].str.lower()

# ==== クラス付け ====
schedule_df["class"] = schedule_df["result"].map({
    "W": "win", "L": "loss", "D": "draw"
}).fillna("upcoming")

# ==== 次の試合（未実施・未来）の1試合に next-game を付加 ====
future_games = schedule_df[(schedule_df["datetime"] > pd.Timestamp.today()) & (schedule_df["score"] == "-")]
if not future_games.empty:
    next_game_idx = future_games["datetime"].idxmin()
    schedule_df.loc[next_game_idx, "class"] = "next-game"

# ==== BYE処理 ====
bye_mask = schedule_df["opponent"].str.upper() == "BYE"
schedule_df.loc[bye_mask, ["venue", "venue_class", "score", "result"]] = ""
schedule_df.loc[bye_mask, "class"] = "bye"

# ==== 色情報付与 ====
colors_df.columns = [col.strip() for col in colors_df.columns]
colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
schedule_df = pd.merge(schedule_df, colors_df, on="opponent", how="left")

# ==== スライドHTML出力関数（時間表記調整済） ====
def build_scorebar_slides_with_date_rules(schedule_df):
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    html = ""
    for _, row in schedule_df.iterrows():
        dt = row["datetime"]
        raw_str = str(row.get("datetime_str", ""))
        week = row["week"]
        opponent = row["opponent"]
        row_class = row["class"]
        date_iso = dt.isoformat() if pd.notna(dt) else ""

        # .line1 表示処理
        is_bye = str(opponent).upper() == "BYE"
        week_html = f"<span class='week'>{week}</span>"

        if is_bye:
            line1_text = week_html
        elif pd.isna(dt):
            line1_text = f"{week_html}　TBD"
        else:
            weekday = weekdays[dt.weekday()]
            date_str = f"{dt.month}/{dt.day} ({weekday})"
            if ":" in raw_str:
                time_str = dt.strftime("%H:%M")
                line1_text = f"{week_html}　{date_str} {time_str} JST"
            else:
                line1_text = f"{week_html}　{date_str} TBD"

        # BYE週
        if str(opponent).upper() == "BYE":
            html += f"""
<div class='schedule-slide {row_class}' data-date='{date_iso}'>
  <div class='line1'>{line1_text}</div>
  <div class='line2'>
    <span class='opponent'>BYE</span>
  </div>
</div>
"""
            continue

        # 通常試合
        score = row["score"]
        result = row["result"]
        venue = "home" if row["venue_class"] == "home" else "away"
        symbol = "vs" if venue == "home" else "@"
        bg = row["bg"] or "#ccc"
        fg = row["fg"] or "#000"
        result_display = f"{result} {score}" if result in ["W", "L", "D"] else score

        html += f"""
<div class='schedule-slide {row_class}' data-date='{date_iso}'>
  <div class='line1'>{line1_text}</div>
  <div class='line2'>
    <span class='opponent'>
      <span class='venue {venue}'>{symbol}</span>
      <span class='team-badge' style='background: {bg}; color: {fg};'>{opponent}</span>
    </span>
    <span class='result'>{result_display}</span>
  </div>
</div>
"""
    return html.strip()

# ==== 出力 ====
print('<div id="score-bar"><div class="schedule-carousel-wrapper">')
print('<button class="schedule-nav schedule-prev">◀</button>')
print('<div class="schedule-carousel-viewport"><div class="schedule-carousel">')
print(build_scorebar_slides_with_date_rules(schedule_df))
print('</div></div>')
print('<button class="schedule-nav schedule-next">▶</button></div></div>')
