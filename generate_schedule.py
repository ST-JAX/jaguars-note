import pandas as pd
import sys
import os
import unicodedata

# ==== 入力チェック ====
if len(sys.argv) < 2:
    print("[使い方] generate_schedule.py [試合CSVファイル]")
    sys.exit(1)

csv_path = sys.argv[1]
script_dir = os.path.dirname(os.path.abspath(__file__))
color_path = os.path.join(script_dir, "team_color.xlsx")

# ==== チーム → (カンファレンス, ディビジョン) マップ ====
# schedule_df["opponent"] の表記に合わせて必要に応じて調整してください。
TEAM_INFO = {
    # AFC South
    "JAX": ("AFC", "South"),
    "HOU": ("AFC", "South"),
    "IND": ("AFC", "South"),
    "TEN": ("AFC", "South"),
    # AFC East
    "BUF": ("AFC", "East"),
    "MIA": ("AFC", "East"),
    "NYJ": ("AFC", "East"),
    "NE": ("AFC", "East"),
    # AFC North
    "BAL": ("AFC", "North"),
    "PIT": ("AFC", "North"),
    "CLE": ("AFC", "North"),
    "CIN": ("AFC", "North"),
    # AFC West
    "KC": ("AFC", "West"),
    "LAC": ("AFC", "West"),
    "DEN": ("AFC", "West"),
    "LV": ("AFC", "West"),
    # NFC East
    "PHI": ("NFC", "East"),
    "DAL": ("NFC", "East"),
    "NYG": ("NFC", "East"),
    "WSH": ("NFC", "East"),  # CSV で WAS を使っているなら "WAS": (...) に変更
    # NFC North
    "GB": ("NFC", "North"),
    "MIN": ("NFC", "North"),
    "CHI": ("NFC", "North"),
    "DET": ("NFC", "North"),
    # NFC South
    "TB": ("NFC", "South"),
    "NO": ("NFC", "South"),
    "ATL": ("NFC", "South"),
    "CAR": ("NFC", "South"),
    # NFC West
    "SF": ("NFC", "West"),
    "SEA": ("NFC", "West"),
    "LAR": ("NFC", "West"),
    "ARI": ("NFC", "West"),
}

JAX_CONF = "AFC"
JAX_DIV = "South"

# ==== データ読み込み ====
schedule_df = pd.read_csv(csv_path, dtype=str)
colors_df = pd.read_excel(color_path)

# カラム名を正規化（全角→半角・前後の空白削除）
schedule_df.columns = [unicodedata.normalize("NFKC", str(c)).strip() for c in schedule_df.columns]

# ==== カラム整形 ====
schedule_df = schedule_df.rename(
    columns={
        "Week": "week",
        "チーム": "opponent",
        "Home/Away": "home",
        "Score": "score",
        "Win/Lose": "win",
    }
)

# ==== 日時整形 ====
time_col = "試合日時(日本時間)"  # 正規化後のカラム名
if time_col in schedule_df.columns:
    datetime_clean = schedule_df[time_col].fillna("").astype(str).str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
else:
    datetime_clean = pd.Series([""] * len(schedule_df))

parsed_dt = pd.to_datetime(datetime_clean, errors="coerce")
schedule_df["datetime"] = parsed_dt

datetime_str = []
for raw, dt in zip(datetime_clean, parsed_dt):
    if pd.isna(dt):
        datetime_str.append("TBD")
    elif ":" not in raw:
        datetime_str.append(dt.strftime("%Y/%m/%d") + " TBD")
    else:
        datetime_str.append(dt.strftime("%Y/%m/%d %H:%M"))
schedule_df["datetime_str"] = datetime_str

# ==== 勝敗マッピング ====
schedule_df["result"] = schedule_df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")

# ==== venue 表示 ====
schedule_df["venue"] = schedule_df["home"].map({"Home": "Home", "Away": "Away"}).fillna("")
schedule_df["venue_class"] = schedule_df["venue"].str.lower()

# ==== スコア補完 ====
schedule_df["score"] = schedule_df["score"].fillna("-")

# ==== クラス付け ====
schedule_df["class"] = schedule_df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

# ==== 次の試合（未実施・未来）の1試合に next-game を付加 ====
future_games = schedule_df[(schedule_df["datetime"] > pd.Timestamp.today()) & (schedule_df["score"] == "-")]
if not future_games.empty:
    next_game_idx = future_games["datetime"].idxmin()
    schedule_df.loc[next_game_idx, "class"] = "next-game"

# ==== BYE処理 ====
bye_mask = schedule_df["opponent"].str.upper() == "BYE"
schedule_df.loc[bye_mask, ["datetime_str", "venue", "venue_class", "score", "result"]] = ""
schedule_df.loc[bye_mask, "class"] = "bye"

# ==== 色情報付与 ====
colors_df.columns = [col.strip() for col in colors_df.columns]
colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
schedule_df = pd.merge(schedule_df, colors_df, on="opponent", how="left")

# ==== 日付と時刻を分割（スマホ用） ====
schedule_df["date"] = schedule_df["datetime"].dt.strftime("%Y/%m/%d")
schedule_df["time"] = schedule_df["datetime"].dt.strftime("%H:%M")


# ==== JAX 戦績バー用ヘルパー（Scheduleページ用） ====


def _filter_regular_schedule(df):
    """Pre Week を除いたレギュラーシーズンのみ抽出"""
    if "week" not in df.columns:
        return df.copy()
    s = df["week"].astype(str)
    return df[~s.str.startswith("Pre")].copy()


def _format_record_schedule(w, l, t):
    """(W, L, T) → 'W-L(-T)' 形式の文字列"""
    return f"{w}-{l}" + (f"-{t}" if t > 0 else "")


def _count_record_schedule(df, win_col="win"):
    """与えられた試合群から W-L(-T) を計算"""
    if df.empty or win_col not in df.columns:
        return ""
    wins = (df[win_col] == "Win").sum()
    losses = (df[win_col] == "Lose").sum()
    ties = (df[win_col] == "Draw").sum()
    return _format_record_schedule(int(wins), int(losses), int(ties))


def _compute_home_away_schedule(df, loc):
    """Home / Away 別の戦績を集計（終わった試合だけ）"""
    if "home" not in df.columns or "win" not in df.columns:
        return ""
    sub = df[(df["home"] == loc) & (df["win"].isin(["Win", "Lose", "Draw"]))]
    return _count_record_schedule(sub, "win")


def _compute_streak_schedule(df):
    """直近の連勝 / 連敗 / 引き分け数を計算 (W2, L3, D1 など)"""
    if "win" not in df.columns or df.empty:
        return ""
    results = [r for r in df["win"].tolist() if isinstance(r, str) and r.strip() != "" and r in ("Win", "Lose", "Draw")]
    if not results:
        return ""
    last = results[-1]
    code_map = {"Win": "W", "Lose": "L", "Draw": "D"}
    code = code_map.get(last)
    if not code:
        return ""
    count = 0
    for r in reversed(results):
        if r == last:
            count += 1
        else:
            break
    return f"{code}{count}"


def build_schedule_record_bar(schedule_df):
    """
    スケジュール固定ページ用の戦績バー HTML を生成
    - Preseason を除く
    - 終わった試合（win列が Win/Lose/Draw）のみで集計
    - Div_Record / Conference_Record カラムには依存しない
    """

    df = schedule_df.copy()
    reg = _filter_regular_schedule(df)

    # 「終わった試合」＝ win が入っている行だけ
    played = reg[reg["win"].isin(["Win", "Lose", "Draw"])].copy()

    # まだシーズン前なら 0-0 だけ出す
    if played.empty:
        html = """
<div id="schedule-record-bar">
  <div class="jax-record-inner">
    <div class="jax-record-main">
      <span class="jax-record-team">JAX</span>
      <span class="jax-record-overall">0-0</span>
    </div>
  </div>
</div>""".strip()
        return html

    # 全体戦績
    overall = _count_record_schedule(played, "win")

    # opponent から conf/div を付与
    conf_div_df = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div_df.columns = ["_opp_conf", "_opp_div"]
    played = played.join(conf_div_df)

    # Division（同カンファレンスかつ同ディビジョン）
    div_games = played[(played["_opp_conf"] == JAX_CONF) & (played["_opp_div"] == JAX_DIV)]
    div_record = _count_record_schedule(div_games, "win")

    # Conference（同カンファレンスの全試合）
    conf_games = played[played["_opp_conf"] == JAX_CONF]
    conf_record = _count_record_schedule(conf_games, "win")

    # NFC（相手がNFC）
    nfc_games = played[played["_opp_conf"] == "NFC"]
    nfc_record = _count_record_schedule(nfc_games, "win")

    # Home / Away
    home_record = _compute_home_away_schedule(played, "Home")
    away_record = _compute_home_away_schedule(played, "Away")

    # Streak（W/L/D 連続）
    streak = _compute_streak_schedule(played)

    # Division pill（常時表示）
    division_pill_html = ""
    if div_record:
        division_pill_html = (
            "<span class='jax-record-pill jax-record-pill-division'>"
            "<span class='jax-record-label'>Division</span> "
            f"<span class='jax-record-num'>{div_record}</span>"
            "</span>"
        )

    # 折りたたみ無しで全部見せる pill
    pills = []

    if conf_record:
        pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>Conference</span> "
            f"<span class='jax-record-num'>{conf_record}</span>"
            "</span>"
        )
    if nfc_record:
        pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>NFC</span> "
            f"<span class='jax-record-num'>{nfc_record}</span>"
            "</span>"
        )
    if home_record:
        pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>Home</span> "
            f"<span class='jax-record-num'>{home_record}</span>"
            "</span>"
        )
    if away_record:
        pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>Away</span> "
            f"<span class='jax-record-num'>{away_record}</span>"
            "</span>"
        )

    # Streak：W2+ / L2+ / D2+ を表示
    if streak and streak[0] in ["W", "L", "D"]:
        try:
            n = int(streak[1:])
        except ValueError:
            n = 0

        if n >= 2:
            cls = ["jax-record-streak"]
            if streak.startswith("L"):
                cls.append("jax-record-streak-loss")
            elif streak.startswith("D"):
                cls.append("jax-record-streak-draw")
            class_str = " ".join(cls)

            pills.append(
                f"<span class='jax-record-pill {class_str}'>"
                "<span class='jax-record-label'>Streak</span> "
                f"<span class='jax-record-num'>{streak}</span>"
                "</span>"
            )

    pills_html = "\n        ".join(pills)

    html = f"""
<div id="schedule-record-bar">
  <div class="jax-record-inner">
    <div class="jax-record-main">
      <span class="jax-record-team">JAX</span>
      <span class="jax-record-overall">{overall}</span>
      {division_pill_html}
    </div>
    <div class="jax-record-splits">
      {pills_html}
    </div>
  </div>
</div>""".strip()
    return html


# ==== 出力関数 ====
def build_pc_table(schedule_df):
    html = """
<div class="schedule-desktop">
<table class="schedule-table">
<thead><tr>
<th>Week</th><th>Date & Time</th><th>Opponent</th><th>Home/Away</th><th>Score</th><th>Result</th>
</tr></thead><tbody>
"""
    for _, row in schedule_df.iterrows():
        venue_class = f"venue {row['venue_class']}" if row["venue_class"] else ""
        if str(row["opponent"]).upper() == "BYE":
            opponent_html = "BYE"
        else:
            bg = row.get("bg", "#ccc")
            fg = row.get("fg", "#000")
            opponent_html = f'<span class="team-badge" style="background:{bg};color:{fg};">{row["opponent"]}</span>'
        html += (
            f'<tr class="{row["class"]}">'
            f'<th scope="row">{row["week"]}</th>'
            f'<td>{row["datetime_str"]}</td>'
            f"<td>{opponent_html}</td>"
            f'<td class="{venue_class}">{row["venue"]}</td>'
            f'<td>{row["score"]}</td>'
            f'<td>{row["result"]}</td></tr>\n'
        )
    html += "</tbody></table>\n</div>\n"
    return html


def build_mobile_table(schedule_df):
    html = """
<div class="schedule-mobile">
<table class="schedule-table mobile-compact">
<thead>
  <tr><th>Week</th><th>Date</th><th>Opponent</th><th>Score</th></tr>
</thead>
<tbody>
"""
    for _, row in schedule_df.iterrows():
        is_bye = str(row.get("opponent", "")).upper() == "BYE"
        week = row.get("week", "")
        row_class = row.get("class", "upcoming")

        if is_bye:
            html += f"""
<tr class="{row_class}">
  <td>{week}</td>
  <td></td>
  <td>BYE</td>
  <td></td>
</tr>
"""
        else:
            date = row.get("date", "")
            time = row.get("time", "") or "TBD"
            venue = row.get("venue_class", "")
            opponent = row.get("opponent", "")
            score = row.get("score", "-")
            result = row.get("result", "").strip()
            bg = row.get("bg", "#ccc")
            fg = row.get("fg", "#000")

            symbol = "vs" if venue == "home" else "@"
            venue_class = f"venue {venue}"
            result_class = f"result {row_class}" if result in ["W", "L", "D"] else "result"
            result_html = f'<small class="{result_class}">{result}</small>' if result in ["W", "L", "D"] else ""

            opponent_html = (
                f'<span class="{venue_class}">{symbol}</span>'
                f'<span class="team-badge" style="background:{bg}; color:{fg};">{opponent}</span>'
            )

            html += f"""
<tr class="{row_class}">
  <td>{week}</td>
  <td>{date}<br><small>{time}</small></td>
  <td>{opponent_html}</td>
  <td>{score}<br>{result_html}</td>
</tr>
"""
    html += "</tbody></table>\n</div>\n"
    return html


# ==== Pre / Regular に分割して出力 ====
pre_df = schedule_df[schedule_df["week"].astype(str).str.startswith("Pre")]
reg_df = schedule_df[~schedule_df["week"].astype(str).str.startswith("Pre")]

print(build_schedule_record_bar(schedule_df))

print('<div class="tab-buttons">')
print('<button class="tab-btn active" data-target="pre">Preseason</button>')
print('<button class="tab-btn" data-target="reg">Regular Season</button>')
print("</div>")

print('<div class="tab-content" id="pre">')
print(build_pc_table(pre_df))
print(build_mobile_table(pre_df))
print("</div>")

print('<div class="tab-content" id="reg">')
print(build_pc_table(reg_df))
print(build_mobile_table(reg_df))
print("</div>")
