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

# ポストシーズンの識別子を定義
POSTSEASON_WEEKS = ["WC", "DIV", "CONF", "SB"]

TEAM_INFO = {
    "JAX": ("AFC", "South"), "HOU": ("AFC", "South"), "IND": ("AFC", "South"), "TEN": ("AFC", "South"),
    "BUF": ("AFC", "East"), "MIA": ("AFC", "East"), "NYJ": ("AFC", "East"), "NE": ("AFC", "East"),
    "BAL": ("AFC", "North"), "PIT": ("AFC", "North"), "CLE": ("AFC", "North"), "CIN": ("AFC", "North"),
    "KC": ("AFC", "West"), "LAC": ("AFC", "West"), "DEN": ("AFC", "West"), "LV": ("AFC", "West"),
    "PHI": ("NFC", "East"), "DAL": ("NFC", "East"), "NYG": ("NFC", "East"), "WAS": ("NFC", "East"),
    "GB": ("NFC", "North"), "MIN": ("NFC", "North"), "CHI": ("NFC", "North"), "DET": ("NFC", "North"),
    "TB": ("NFC", "South"), "NO": ("NFC", "South"), "ATL": ("NFC", "South"), "CAR": ("NFC", "South"),
    "SF": ("NFC", "West"), "SEA": ("NFC", "West"), "LAR": ("NFC", "West"), "ARI": ("NFC", "West"),
}
JAX_CONF, JAX_DIV = "AFC", "South"

# ==== データ読み込み ====
schedule_df = pd.read_csv(csv_path, dtype=str)
colors_df = pd.read_excel(color_path)
schedule_df.columns = [unicodedata.normalize("NFKC", str(c)).strip() for c in schedule_df.columns]

schedule_df = schedule_df.rename(
    columns={"Week": "week", "チーム": "opponent", "Home/Away": "home", "Score": "score", "Win/Lose": "win"}
)

# ==== 日時整形 ====
time_col = "試合日時(日本時間)"
if time_col in schedule_df.columns:
    datetime_clean = schedule_df[time_col].fillna("").astype(str).str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
else:
    datetime_clean = pd.Series([""] * len(schedule_df))

parsed_dt = pd.to_datetime(datetime_clean, errors="coerce")
schedule_df["datetime"] = parsed_dt

datetime_str = []
for raw, dt in zip(datetime_clean, parsed_dt):
    if pd.isna(dt): datetime_str.append("TBD")
    elif ":" not in raw: datetime_str.append(dt.strftime("%Y/%m/%d") + " TBD")
    else: datetime_str.append(dt.strftime("%Y/%m/%d %H:%M"))
schedule_df["datetime_str"] = datetime_str

schedule_df["result"] = schedule_df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")
schedule_df["venue"] = schedule_df["home"].map({"Home": "Home", "Away": "Away"}).fillna("")
schedule_df["venue_class"] = schedule_df["venue"].str.lower()
schedule_df["score"] = schedule_df["score"].fillna("-")
schedule_df["class"] = schedule_df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

# 次の試合
future_games = schedule_df[(schedule_df["datetime"] > pd.Timestamp.today()) & (schedule_df["score"] == "-")]
if not future_games.empty:
    schedule_df.loc[future_games["datetime"].idxmin(), "class"] = "next-game"

# BYE
bye_mask = schedule_df["opponent"].str.upper() == "BYE"
schedule_df.loc[bye_mask, ["datetime_str", "venue", "venue_class", "score", "result"]] = ""
schedule_df.loc[bye_mask, "class"] = "bye"

# 色
colors_df.columns = [col.strip() for col in colors_df.columns]
colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
schedule_df = pd.merge(schedule_df, colors_df, on="opponent", how="left")
schedule_df["date"] = schedule_df["datetime"].dt.strftime("%Y/%m/%d")
schedule_df["time"] = schedule_df["datetime"].dt.strftime("%H:%M")

def build_schedule_record_bar(schedule_df):
    reg = schedule_df[~schedule_df["week"].astype(str).str.startswith("Pre") & ~schedule_df["week"].isin(POSTSEASON_WEEKS)].copy()
    played = reg[reg["win"].isin(["Win", "Lose", "Draw"])].copy()
    if played.empty: return '<div id="schedule-record-bar"><div class="jax-record-inner"><div class="jax-record-main"><span class="jax-record-team">JAX</span><span class="jax-record-overall">0-0</span></div></div></div>'
    
    wins, losses, ties = (played["win"] == "Win").sum(), (played["win"] == "Lose").sum(), (played["win"] == "Draw").sum()
    overall = f"{wins}-{losses}" + (f"-{ties}" if ties > 0 else "")
    
    conf_div_df = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div_df.columns = ["_opp_conf", "_opp_div"]
    played = played.join(conf_div_df)
    
    div_q = played[(played["_opp_conf"] == JAX_CONF) & (played["_opp_div"] == JAX_DIV)]
    div_record = f"{(div_q['win']=='Win').sum()}-{(div_q['win']=='Lose').sum()}"
    
    return f"""<div id="schedule-record-bar"><div class="jax-record-inner"><div class="jax-record-main"><span class="jax-record-team">JAX</span><span class="jax-record-overall">{overall}</span><span class='jax-record-pill jax-record-pill-division'><span class='jax-record-label'>Division</span> <span class='jax-record-num'>{div_record}</span></span></div></div></div>"""

def build_pc_table(df):
    html = '<div class="schedule-desktop"><table class="schedule-table"><thead><tr><th>Week</th><th>Date & Time</th><th>Opponent</th><th>Home/Away</th><th>Score</th><th>Result</th></tr></thead><tbody>'
    for _, row in df.iterrows():
        opp = "BYE" if str(row["opponent"]).upper() == "BYE" else f'<span class="team-badge" style="background:{row.get("bg","#ccc")};color:{row.get("fg","#000")};">{row["opponent"]}</span>'
        html += f'<tr class="{row["class"]}"><th scope="row">{row["week"]}</th><td>{row["datetime_str"]}</td><td>{opp}</td><td class="venue {row["venue_class"]}">{row["venue"]}</td><td>{row["score"]}</td><td>{row["result"]}</td></tr>'
    return html + "</tbody></table></div>"

def build_mobile_table(df):
    html = '<div class="schedule-mobile"><table class="schedule-table mobile-compact"><thead><tr><th>Week</th><th>Date</th><th>Opponent</th><th>Score</th></tr></thead><tbody>'
    for _, row in df.iterrows():
        if str(row.get("opponent", "")).upper() == "BYE":
            html += f'<tr class="{row["class"]}"><td>{row["week"]}</td><td></td><td>BYE</td><td></td></tr>'
        else:
            sym = "vs" if row["venue_class"] == "home" else "@"
            res_html = f'<small class="result {row["class"]}">{row["result"]}</small>' if row["result"] in ["W","L","D"] else ""
            opp_html = f'<span class="venue {row["venue_class"]}">{sym}</span><span class="team-badge" style="background:{row.get("bg","#ccc")}; color:{row.get("fg","#000")};">{row["opponent"]}</span>'
            html += f'<tr class="{row["class"]}"><td>{row["week"]}</td><td>{row["date"]}<br><small>{row["time"] or "TBD"}</small></td><td>{opp_html}</td><td>{row["score"]}<br>{res_html}</td></tr>'
    return html + "</tbody></table></div>"

# データ分割
pre_df = schedule_df[schedule_df["week"].astype(str).str.startswith("Pre")]
reg_df = schedule_df[~schedule_df["week"].astype(str).str.startswith("Pre") & ~schedule_df["week"].isin(POSTSEASON_WEEKS)]
post_df = schedule_df[schedule_df["week"].isin(POSTSEASON_WEEKS)]

print(build_schedule_record_bar(schedule_df))
print('<div class="tab-buttons">')
print('<button class="tab-btn active" data-target="pre">Preseason</button>')
print('<button class="tab-btn" data-target="reg">Regular Season</button>')
if not post_df.empty:
    print('<button class="tab-btn" data-target="post">Postseason</button>')
print("</div>")

for tid, tdf in [("pre", pre_df), ("reg", reg_df), ("post", post_df)]:
    if tid == "post" and tdf.empty: continue
    print(f'<div class="tab-content {"active" if tid=="pre" else ""}" id="{tid}">')
    print(build_pc_table(tdf))
    print(build_mobile_table(tdf))
    print("</div>")
