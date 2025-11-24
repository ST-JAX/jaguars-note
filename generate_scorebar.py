import pandas as pd
import sys
import os
from datetime import datetime
import unicodedata

# ==== 入力チェック ====
if len(sys.argv) < 2:
    print("[使い方] generate_scorebar.py [試合CSVファイル]")
    sys.exit(1)

csv_path = sys.argv[1]
script_dir = os.path.dirname(os.path.abspath(__file__))
color_path = os.path.join(script_dir, "team_color.xlsx")

# ==== チーム → (カンファレンス, ディビジョン) マップ ====
# ※ schedule_df["opponent"] の表記に合わせて必要に応じて調整してください。
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
    "WAS": ("NFC", "East"),  # or "WAS" など、CSVに合わせて変更
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
# カラム名を正規化（全角→半角・前後の空白削除）
schedule_df.columns = [unicodedata.normalize("NFKC", str(c)).strip() for c in schedule_df.columns]
colors_df = pd.read_excel(color_path)

# ==== カラム整形 ====
# 英語カラムだけ扱いやすい名前に変更（日本語日時カラムはそのまま）
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
# 日本時間の日時カラム名（正規化後）
time_col = "試合日時(日本時間)"

if time_col in schedule_df.columns:
    datetime_clean = schedule_df[time_col].fillna("").astype(str).str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
else:
    # 念のためカラムが無い場合に備えて空文字列で埋める
    datetime_clean = pd.Series([""] * len(schedule_df))

parsed_dt = pd.to_datetime(datetime_clean, errors="coerce")
schedule_df["datetime"] = parsed_dt
schedule_df["datetime_str"] = datetime_clean

# ==== 勝敗・スコア処理 ====
schedule_df["result"] = schedule_df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")
schedule_df["score"] = schedule_df["score"].fillna("-")

# ==== venue 表示 ====
schedule_df["venue"] = schedule_df["home"].map({"Home": "Home", "Away": "Away"}).fillna("")
schedule_df["venue_class"] = schedule_df["venue"].str.lower()

# ==== クラス付け ====
schedule_df["class"] = schedule_df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

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
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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


# ==== JAX 戦績バー用の関数 ====


def _filter_regular(df):
    """Pre Week を除いたレギュラーシーズンのみ抽出"""
    # 正規化後のカラム名に対応（week / Week のどちらもOK）
    week_col = "week" if "week" in df.columns else ("Week" if "Week" in df.columns else None)
    if not week_col:
        return df.copy()
    s = df[week_col].astype(str)
    return df[~s.str.startswith("Pre")].copy()


def _format_record(w, l, t):
    """(W, L, T) → 'W-L(-T)' 形式の文字列"""
    return f"{w}-{l}" + (f"-{t}" if t > 0 else "")


def _count_record(df, win_col):
    """与えられた試合群から W-L(-T) を計算"""
    if df.empty or win_col not in df.columns:
        return ""
    wins = (df[win_col] == "Win").sum()
    losses = (df[win_col] == "Lose").sum()
    ties = (df[win_col] == "Draw").sum()
    return _format_record(int(wins), int(losses), int(ties))


def _compute_home_away_played(df, loc, home_col, win_col):
    """Home / Away 別の戦績を集計（終わった試合だけ）"""
    if home_col not in df.columns or win_col not in df.columns:
        return ""
    sub = df[(df[home_col] == loc) & (df[win_col].isin(["Win", "Lose", "Draw"]))]
    return _count_record(sub, win_col)


def _compute_streak_played(df, win_col):
    """直近の連勝 / 連敗 / 引き分け数を計算 (W2, L3, D1 など)"""
    if win_col not in df.columns or df.empty:
        return ""
    results = [
        r for r in df[win_col].tolist() if isinstance(r, str) and r.strip() != "" and r in ("Win", "Lose", "Draw")
    ]
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


def _guess_season_year(df):
    """datetime または 日本語日時カラムからシーズン年を推測"""
    # 1. datetime カラム（datetime 型）を優先
    if "datetime" in df.columns:
        series = df["datetime"].dropna()
        if not series.empty:
            first = series.iloc[0]
            if isinstance(first, datetime):
                return first.year
            txt = str(first)
            for i in range(len(txt) - 3):
                seg = txt[i : i + 4]
                if seg.isdigit():
                    return int(seg)

    # 2. 日本語日時カラムから推測
    for col in ["試合日時(日本時間)", "試合日時（日本時間）"]:
        if col in df.columns:
            series = df[col].dropna()
            if not series.empty:
                txt = str(series.iloc[0])
                for i in range(len(txt) - 3):
                    seg = txt[i : i + 4]
                    if seg.isdigit():
                        return int(seg)

    # 3. どうしても分からない場合は今年
    return datetime.now().year


def build_jax_record_bar(schedule_df):
    """JAX 戦績バーの HTML を生成（ヘッダーに Division、その他は折りたたみ）
    Div_Record / Conference_Record カラムには依存せず、
    opponent + win から全て計算する。
    """

    df = schedule_df.copy()

    # カラム名（win/home）は rename 済みのものを優先
    win_col = "win" if "win" in df.columns else ("Win/Lose" if "Win/Lose" in df.columns else None)
    home_col = "home" if "home" in df.columns else ("Home/Away" if "Home/Away" in df.columns else None)

    # Win/Lose 情報が無い場合は 0-0 バーだけ出して終了
    if not win_col:
        html = """
<div id="jax-record-bar" class="jax-record-collapsible">
  <div class="jax-record-inner">
    <button class="jax-record-main" type="button" aria-expanded="false">
      <span class="jax-record-team">JAX</span>
      <span class="jax-record-overall">0-0</span>
      <span class="jax-record-chevron" aria-hidden="true">▼</span>
    </button>
    <div class="jax-record-details">
      <div class="jax-record-splits"></div>
    </div>
  </div>
</div>""".strip()
        return html

    # Pre Week を除外
    reg = _filter_regular(df)

    # 「終わった試合」＝ win_col が入っている行だけ
    played = reg[reg[win_col].isin(["Win", "Lose", "Draw"])].copy()

    # まだシーズン前なら 0-0 だけ
    if played.empty:
        season_year = _guess_season_year(reg if not reg.empty else df)
        html = f"""
<div id="jax-record-bar" class="jax-record-collapsible">
  <div class="jax-record-inner">
    <button class="jax-record-main" type="button" aria-expanded="false">
      <span class="jax-record-team">JAX</span>
      <span class="jax-record-overall">0-0</span>
      <span class="jax-record-chevron" aria-hidden="true">▼</span>
    </button>
    <div class="jax-record-details">
      <div class="jax-record-splits"></div>
    </div>
  </div>
</div>""".strip()
        return html

    # 全体戦績は played から計算
    overall = _count_record(played, win_col)

    # ---- opponent から conf / div を付与 ----
    if not played.empty:
        conf_div_df = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
        conf_div_df.columns = ["_opp_conf", "_opp_div"]
        played = played.join(conf_div_df)
    else:
        played["_opp_conf"] = None
        played["_opp_div"] = None

    # Division（同カンファレンスかつ同ディビジョン）
    div_games = played[(played["_opp_conf"] == JAX_CONF) & (played["_opp_div"] == JAX_DIV)]
    div_record = _count_record(div_games, win_col)

    # Conference（同カンファレンスの全試合）
    conf_games = played[played["_opp_conf"] == JAX_CONF]
    conf_record = _count_record(conf_games, win_col)

    # NFC（相手がNFC）
    nfc_games = played[played["_opp_conf"] == "NFC"]
    nfc_record = _count_record(nfc_games, win_col)

    # Home / Away
    home_record = _compute_home_away_played(played, "Home", home_col, win_col) if home_col else ""
    away_record = _compute_home_away_played(played, "Away", home_col, win_col) if home_col else ""

    # Streak（W/L/D 連続）
    streak = _compute_streak_played(played, win_col)

    # ---------- pill を分けて構築 ----------
    # 常に見せるのは Division だけ
    division_pill_html = ""
    if div_record:
        division_pill_html = (
            "<span class='jax-record-pill jax-record-pill-division'>"
            "<span class='jax-record-label'>Division</span> "
            f"<span class='jax-record-num'>{div_record}</span>"
            "</span>"
        )

    # 折りたたみ内に入れる pill 達
    fold_pills = []

    if conf_record:
        fold_pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>Conference</span> "
            f"<span class='jax-record-num'>{conf_record}</span>"
            "</span>"
        )
    if nfc_record:
        fold_pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>NFC</span> "
            f"<span class='jax-record-num'>{nfc_record}</span>"
            "</span>"
        )
    if home_record:
        fold_pills.append(
            "<span class='jax-record-pill'>"
            "<span class='jax-record-label'>Home</span> "
            f"<span class='jax-record-num'>{home_record}</span>"
            "</span>"
        )
    if away_record:
        fold_pills.append(
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

            fold_pills.append(
                f"<span class='jax-record-pill {class_str}'>"
                "<span class='jax-record-label'>Streak</span> "
                f"<span class='jax-record-num'>{streak}</span>"
                "</span>"
            )

    fold_pills_html = "\n        ".join(fold_pills)

    # ---------- HTML ----------
    html = f"""
<div id="jax-record-bar" class="jax-record-collapsible">
  <div class="jax-record-inner">
    <button class="jax-record-main" type="button" aria-expanded="false">
      <span class="jax-record-team">JAX</span>
      <span class="jax-record-overall">{overall}</span>
      {division_pill_html}
      <span class="jax-record-chevron" aria-hidden="true">▼</span>
    </button>
    <div class="jax-record-details">
      <div class="jax-record-splits">
        {fold_pills_html}
      </div>
    </div>
  </div>
</div>""".strip()
    return html


# ==== 出力 ====
# スケジュール + JAX戦績バーをまとめたラッパー
print("<div id='score-wrapper'>")

# ① スケジュールバー
print('<div id="score-bar"><div class="schedule-carousel-wrapper">')
print('<button class="schedule-nav schedule-prev">◀</button>')
print('<div class="schedule-carousel-viewport"><div class="schedule-carousel">')
print(build_scorebar_slides_with_date_rules(schedule_df))
print("</div></div>")
print('<button class="schedule-nav schedule-next">▶</button></div></div>')

# ② スケジュールとの区切り線
print('<div class="header-divider"></div>')

# ③ JAX 戦績バー
print(build_jax_record_bar(schedule_df))

print("</div>")  # score-wrapper 終わり
