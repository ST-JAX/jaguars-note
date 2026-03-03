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

# ポストシーズンの識別子
POSTSEASON_WEEKS = ["WC", "DIV", "CONF", "SB"]

# ==== チーム → (カンファレンス, ディビジョン) マップ ====
TEAM_INFO = {
    "JAX": ("AFC", "South"),
    "HOU": ("AFC", "South"),
    "IND": ("AFC", "South"),
    "TEN": ("AFC", "South"),
    "BUF": ("AFC", "East"),
    "MIA": ("AFC", "East"),
    "NYJ": ("AFC", "East"),
    "NE": ("AFC", "East"),
    "BAL": ("AFC", "North"),
    "PIT": ("AFC", "North"),
    "CLE": ("AFC", "North"),
    "CIN": ("AFC", "North"),
    "KC": ("AFC", "West"),
    "LAC": ("AFC", "West"),
    "DEN": ("AFC", "West"),
    "LV": ("AFC", "West"),
    "PHI": ("NFC", "East"),
    "DAL": ("NFC", "East"),
    "NYG": ("NFC", "East"),
    "WAS": ("NFC", "East"),
    "GB": ("NFC", "North"),
    "MIN": ("NFC", "North"),
    "CHI": ("NFC", "North"),
    "DET": ("NFC", "North"),
    "TB": ("NFC", "South"),
    "NO": ("NFC", "South"),
    "ATL": ("NFC", "South"),
    "CAR": ("NFC", "South"),
    "SF": ("NFC", "West"),
    "SEA": ("NFC", "West"),
    "LAR": ("NFC", "West"),
    "ARI": ("NFC", "West"),
}
JAX_CONF, JAX_DIV = "AFC", "South"

# ==== データ読み込み ====
schedule_df = pd.read_csv(csv_path, dtype=str)
schedule_df.columns = [unicodedata.normalize("NFKC", str(c)).strip() for c in schedule_df.columns]
colors_df = pd.read_excel(color_path)

schedule_df = schedule_df.rename(
    columns={"Week": "week", "チーム": "opponent", "Home/Away": "home", "Score": "score", "Win/Lose": "win"}
)

# 日時整形
time_col = "試合日時(日本時間)"
datetime_clean = (
    schedule_df[time_col].fillna("").astype(str).str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
    if time_col in schedule_df.columns
    else pd.Series([""] * len(schedule_df))
)
parsed_dt = pd.to_datetime(datetime_clean, errors="coerce")
schedule_df["datetime"] = parsed_dt
schedule_df["datetime_str"] = datetime_clean

schedule_df["result"] = schedule_df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")
schedule_df["score"] = schedule_df["score"].fillna("-")
schedule_df["venue_class"] = schedule_df["home"].map({"Home": "home", "Away": "away"}).fillna("")
schedule_df["class"] = schedule_df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

# 次の試合
future = schedule_df[(schedule_df["datetime"] > pd.Timestamp.today()) & (schedule_df["score"] == "-")]
if not future.empty:
    schedule_df.loc[future["datetime"].idxmin(), "class"] = "next-game"

# BYE
bye_mask = schedule_df["opponent"].str.upper() == "BYE"
schedule_df.loc[bye_mask, ["score", "result"]] = ""
schedule_df.loc[bye_mask, "class"] = "bye"

# 色
colors_df.columns = [col.strip() for col in colors_df.columns]
colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
schedule_df = pd.merge(schedule_df, colors_df, on="opponent", how="left")


def build_scorebar_slides(df):
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    html = ""
    for _, row in df.iterrows():
        dt, week, opp = row["datetime"], row["week"], row["opponent"]
        date_iso = dt.isoformat() if pd.notna(dt) else ""
        if str(opp).upper() == "BYE":
            html += f"<div class='schedule-slide bye' data-date='{date_iso}'><div class='line1'><span class='week'>{week}</span></div><div class='line2'><span class='opponent'>BYE</span></div></div>"
            continue
        line1 = (
            f"<span class='week'>{week}</span>　{dt.month}/{dt.day} ({weekdays[dt.weekday()]}) {dt.strftime('%H:%M') if ':' in str(row['datetime_str']) else 'TBD'} JST"
            if pd.notna(dt)
            else f"<span class='week'>{week}</span>　TBD"
        )
        sym = "vs" if row["venue_class"] == "home" else "@"
        res = f"{row['result']} {row['score']}" if row["result"] in ["W", "L", "D"] else row["score"]
        html += f"<div class='schedule-slide {row['class']}' data-date='{date_iso}'><div class='line1'>{line1}</div><div class='line2'><span class='opponent'><span class='venue {row['venue_class']}'>{sym}</span><span class='team-badge' style='background:{row['bg'] or '#ccc'};color:{row['fg'] or '#000'};'>{opp}</span></span><span class='result'>{res}</span></div></div>"
    return html


def _cnt(df, win_col):
    if df.empty:
        return ""
    w, l, t = (df[win_col] == "Win").sum(), (df[win_col] == "Lose").sum(), (df[win_col] == "Draw").sum()
    return f"{int(w)}-{int(l)}" + (f"-{int(t)}" if t > 0 else "")


def build_jax_record_bar(df):
    win_col, home_col = "win", "home"
    reg = df[~df["week"].astype(str).str.startswith("Pre") & ~df["week"].isin(POSTSEASON_WEEKS)].copy()
    played = reg[reg[win_col].isin(["Win", "Lose", "Draw"])].copy()
    if played.empty:
        return '<div id="jax-record-bar" class="jax-record-collapsible"><div class="jax-record-inner"><button class="jax-record-main" type="button"><span class="jax-record-team">JAX</span><span class="jax-record-overall">0-0</span></button></div></div>'

    overall = _cnt(played, win_col)
    conf_div = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div.columns = ["_conf", "_div"]
    played = played.join(conf_div)

    # 各種戦績
    div_rec = _cnt(played[(played["_conf"] == JAX_CONF) & (played["_div"] == JAX_DIV)], win_col)
    conf_rec = _cnt(played[played["_conf"] == JAX_CONF], win_col)
    nfc_rec = _cnt(played[played["_conf"] == "NFC"], win_col)
    h_rec = _cnt(played[played[home_col] == "Home"], win_col)
    a_rec = _cnt(played[played[home_col] == "Away"], win_col)

    # Streak計算
    streak_html = ""
    res_list = [r for r in played[win_col].tolist() if r in ("Win", "Lose", "Draw")]
    if res_list:
        last, count = res_list[-1], 0
        for r in reversed(res_list):
            if r == last:
                count += 1
            else:
                break
        if count >= 2:
            code = {"Win": "W", "Lose": "L", "Draw": "D"}.get(last, "")
            cls = "jax-record-pill jax-record-streak" + (
                " jax-record-streak-loss" if code == "L" else " jax-record-streak-draw" if code == "D" else ""
            )
            streak_html = f"<span class='{cls}'><span class='jax-record-label'>Streak</span> <span class='jax-record-num'>{code}{count}</span></span>"

    pills = []
    if conf_rec:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Conf</span> <span class='jax-record-num'>{conf_rec}</span></span>"
        )
    if nfc_rec:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>NFC</span> <span class='jax-record-num'>{nfc_rec}</span></span>"
        )
    if h_rec:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Home</span> <span class='jax-record-num'>{h_rec}</span></span>"
        )
    if a_rec:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Away</span> <span class='jax-record-num'>{a_rec}</span></span>"
        )
    if streak_html:
        pills.append(streak_html)

    div_disp = (
        f"<span class='jax-record-pill jax-record-pill-division'><span class='jax-record-label'>Div</span> <span class='jax-record-num'>{div_rec}</span></span>"
        if div_rec
        else ""
    )
    return f"""<div id="jax-record-bar" class="jax-record-collapsible"><div class="jax-record-inner"><button class="jax-record-main" type="button" aria-expanded="false"><span class="jax-record-team">JAX</span><span class="jax-record-overall">{overall}</span>{div_disp}<span class="jax-record-chevron" aria-hidden="true">▼</span></button><div class="jax-record-details"><div class="jax-record-splits">{"".join(pills)}</div></div></div></div>"""


print(
    "<div id='score-wrapper'><div id='score-bar'><div class='schedule-carousel-wrapper'><button class='schedule-nav schedule-prev'>◀</button><div class='schedule-carousel-viewport'><div class='schedule-carousel'>"
)
print(build_scorebar_slides(schedule_df))
print("</div></div><button class='schedule-nav schedule-next'>▶</button></div></div><div class='header-divider'></div>")
print(build_jax_record_bar(schedule_df))
print("</div>")
