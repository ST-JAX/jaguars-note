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

# ポストシーズンの識別子（NotionのWeek列と一致させる）
POSTSEASON_WEEKS = ["WC", "DIV", "CONF", "SB"]

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
colors_df = pd.read_excel(color_path)
schedule_df.columns = [unicodedata.normalize("NFKC", str(c)).strip() for c in schedule_df.columns]

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

dt_str = []
for raw, dt in zip(datetime_clean, parsed_dt):
    if pd.isna(dt):
        dt_str.append("TBD")
    else:
        dt_str.append(dt.strftime("%Y/%m/%d") + (" " + dt.strftime("%H:%M") if ":" in raw else " TBD"))
schedule_df["datetime_str"] = dt_str

schedule_df["result"] = schedule_df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")
schedule_df["venue_class"] = schedule_df["home"].map({"Home": "home", "Away": "away"}).fillna("")
schedule_df["score"] = schedule_df["score"].fillna("-")
schedule_df["class"] = schedule_df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

# 次の試合
future = schedule_df[(schedule_df["datetime"] > pd.Timestamp.today()) & (schedule_df["score"] == "-")]
if not future.empty:
    schedule_df.loc[future["datetime"].idxmin(), "class"] = "next-game"

# BYE
bye_mask = schedule_df["opponent"].str.upper() == "BYE"
schedule_df.loc[bye_mask, ["datetime_str", "score", "result"]] = ""
schedule_df.loc[bye_mask, "class"] = "bye"

# 色情報の統合
colors_df.columns = [col.strip() for col in colors_df.columns]
colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
schedule_df = pd.merge(schedule_df, colors_df, on="opponent", how="left")
schedule_df["date"] = schedule_df["datetime"].dt.strftime("%Y/%m/%d")
schedule_df["time"] = schedule_df["datetime"].dt.strftime("%H:%M")


def _cnt(df):
    if df.empty:
        return ""
    w, l, t = (df["win"] == "Win").sum(), (df["win"] == "Lose").sum(), (df["win"] == "Draw").sum()
    return f"{int(w)}-{int(l)}" + (f"-{int(t)}" if t > 0 else "")


def build_schedule_record_bar(df):
    reg = df[~df["week"].astype(str).str.startswith("Pre") & ~df["week"].isin(POSTSEASON_WEEKS)].copy()
    played = reg[reg["win"].isin(["Win", "Lose", "Draw"])].copy()
    if played.empty:
        return '<div id="schedule-record-bar"><div class="jax-record-inner"><div class="jax-record-main"><span class="jax-record-team">JAX</span><span class="jax-record-overall">0-0</span></div></div></div>'

    overall = _cnt(played)
    conf_div = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div.columns = ["_conf", "_div"]
    played = played.join(conf_div)

    div_rec = _cnt(played[(played["_conf"] == JAX_CONF) & (played["_div"] == JAX_DIV)])
    conf_rec = _cnt(played[played["_conf"] == JAX_CONF])
    nfc_rec = _cnt(played[played["_conf"] == "NFC"])
    h_rec = _cnt(played[played["home"] == "Home"])
    a_rec = _cnt(played[played["home"] == "Away"])

    # Streakの計算
    streak_html = ""
    res_list = [r for r in played["win"].tolist() if r in ("Win", "Lose", "Draw")]
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
            f"<span class='jax-record-pill'><span class='jax-record-label'>Conference</span> <span class='jax-record-num'>{conf_rec}</span></span>"
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

    div_pill = (
        f"<span class='jax-record-pill jax-record-pill-division'><span class='jax-record-label'>Division</span> <span class='jax-record-num'>{div_rec}</span></span>"
        if div_rec
        else ""
    )
    return f"<div id='schedule-record-bar'><div class='jax-record-inner'><div class='jax-record-main'><span class='jax-record-team'>JAX</span><span class='jax-record-overall'>{overall}</span>{div_pill}</div><div class='jax-record-splits'>{''.join(pills)}</div></div></div>"


def build_table(df, is_pc):
    if is_pc:
        html = '<div class="schedule-desktop"><table class="schedule-table"><thead><tr><th>Week</th><th>Date & Time</th><th>Opponent</th><th>Home/Away</th><th>Score</th><th>Result</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            opp = (
                "BYE"
                if str(r["opponent"]).upper() == "BYE"
                else f'<span class="team-badge" style="background:{r.get("bg","#ccc")};color:{r.get("fg","#000")};">{r["opponent"]}</span>'
            )
            html += f'<tr class="{r["class"]}"><th scope="row">{r["week"]}</th><td>{r["datetime_str"]}</td><td>{opp}</td><td class="venue {r["venue_class"]}">{r["home"]}</td><td>{r["score"]}</td><td>{r["result"]}</td></tr>'
    else:
        html = '<div class="schedule-mobile"><table class="schedule-table mobile-compact"><thead><tr><th>Week</th><th>Date</th><th>Opponent</th><th>Score</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            if str(r.get("opponent", "")).upper() == "BYE":
                html += f'<tr class="{r["class"]}"><td>{r["week"]}</td><td></td><td>BYE</td><td></td></tr>'
            else:
                sym = "vs" if r["venue_class"] == "home" else "@"
                res = (
                    f'<small class="result {r["class"]}">{r["result"]}</small>'
                    if r["result"] in ["W", "L", "D"]
                    else ""
                )
                opp = f'<span class="venue {r["venue_class"]}">{sym}</span><span class="team-badge" style="background:{r.get("bg","#ccc")}; color:{r.get("fg","#000")};">{r["opponent"]}</span>'
                html += f'<tr class="{r["class"]}"><td>{r["week"]}</td><td>{r["date"]}<br><small>{r["time"] or "TBD"}</small></td><td>{opp}</td><td>{r["score"]}<br>{res}</td></tr>'
    return html + "</tbody></table></div>"


pre_df = schedule_df[schedule_df["week"].astype(str).str.startswith("Pre")]
reg_df = schedule_df[
    ~schedule_df["week"].astype(str).str.startswith("Pre") & ~schedule_df["week"].isin(POSTSEASON_WEEKS)
]
post_df = schedule_df[schedule_df["week"].isin(POSTSEASON_WEEKS)]

# ==== HTML出力 ====
print(build_schedule_record_bar(schedule_df))

print('<div class="tab-buttons">')
for lbl, tid, d in [("Preseason", "pre", pre_df), ("Regular Season", "reg", reg_df), ("Postseason", "post", post_df)]:
    if tid == "post" and d.empty:
        continue
    print(f'<button class="tab-btn" data-target="{tid}">{lbl}</button>')
print("</div>")

for tid, d in [("pre", pre_df), ("reg", reg_df), ("post", post_df)]:
    if tid == "post" and d.empty:
        continue
    print(f'<div class="tab-content" id="{tid}" style="display:none;">')
    print(build_table(d, True))
    print(build_table(d, False))
    print("</div>")

# ==== JavaScript埋め込み ====
print(
    """
<script>
document.addEventListener("DOMContentLoaded", function () {
    const now = new Date();
    const month = now.getMonth() + 1;
    let defaultTab = "reg";

    const hasPost = document.getElementById("post") !== null;
    const hasPre = document.getElementById("pre") !== null;

    if (month >= 5 && month <= 8 && hasPre) {
        defaultTab = "pre";
    } else if ((month === 1 || month === 2) && hasPost) {
        defaultTab = "post";
    } else if (!document.getElementById(defaultTab)) {
        if (hasPost) defaultTab = "post";
        else if (hasPre) defaultTab = "pre";
    }

    document.querySelectorAll(".tab-content").forEach(tab => {
        tab.classList.remove("active");
        tab.style.display = "none";
    });
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.remove("active");
        if (btn.dataset.target === defaultTab) {
            btn.classList.add("active");
        }
    });

    const defaultContent = document.getElementById(defaultTab);
    if (defaultContent) {
        defaultContent.style.display = "block";
        defaultContent.classList.add("active");
    }

    document.querySelectorAll(".tab-btn").forEach(button => {
        button.addEventListener("click", () => {
            const target = button.dataset.target;
            document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");
            document.querySelectorAll(".tab-content").forEach(tab => {
                if (tab.id === target) {
                    tab.style.display = "block";
                    tab.classList.add("active");
                } else {
                    tab.classList.remove("active");
                    tab.style.display = "none";
                }
            });
        });
    });
});
</script>
"""
)
