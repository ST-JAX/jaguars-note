import pandas as pd
import requests
import datetime
import hashlib
import base64
import random
import os
import unicodedata
from xml.sax.saxutils import escape

# ==========================================
# 1. 設定情報（ここを自分の情報に書き換えて！）
# ==========================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_SCHEDULE_DB_ID = os.getenv("NOTION_SCHEDULE_DB_ID")
HATENA_USER = os.getenv("HATENA_USER")
HATENA_BLOG = os.getenv("HATENA_BLOG")
HATENA_API_KEY = os.getenv("HATENA_API_KEY")
HATENA_SCHEDULE_PAGE_ID = os.getenv("HATENA_SCHEDULE_PAGE_ID")
# 【追加箇所】
HATENA_LATEST_SCHEDULE_PAGE_ID = os.getenv("HATENA_LATEST_SCHEDULE_PAGE_ID")

# パス設定
script_dir = os.path.dirname(os.path.abspath(__file__))
color_path = os.path.join(script_dir, "team_color.xlsx")

# チーム情報マップ
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
POSTSEASON_WEEKS = ["WC", "DIV", "CONF", "SB"]

# ==========================================
# 2. ロジック関数群（元のコードを完全に維持）
# ==========================================


def _count_record_schedule(df, win_col="win"):
    if df.empty or win_col not in df.columns:
        return ""
    wins = (df[win_col] == "Win").sum()
    losses = (df[win_col] == "Lose").sum()
    ties = (df[win_col] == "Draw").sum()
    return f"{int(wins)}-{int(losses)}" + (f"-{int(ties)}" if ties > 0 else "")


def _compute_streak_schedule(df):
    if "win" not in df.columns or df.empty:
        return ""
    results = [r for r in df["win"].tolist() if isinstance(r, str) and r.strip() != "" and r in ("Win", "Lose", "Draw")]
    if not results:
        return ""
    last = results[-1]
    count = 0
    for r in reversed(results):
        if r == last:
            count += 1
        else:
            break
    code = {"Win": "W", "Lose": "L", "Draw": "D"}.get(last, "")
    return f"{code}{count}"


def build_schedule_record_bar(schedule_df):
    s = schedule_df["week"].astype(str)
    reg = schedule_df[~s.str.startswith("Pre") & ~schedule_df["week"].isin(POSTSEASON_WEEKS)].copy()
    played = reg[reg["win"].isin(["Win", "Lose", "Draw"])].copy()
    if played.empty:
        return '<div id="schedule-record-bar"><div class="jax-record-inner"><div class="jax-record-main"><span class="jax-record-team">JAX</span><span class="jax-record-overall">0-0</span></div></div></div>'

    overall = _count_record_schedule(played)
    conf_div_df = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div_df.columns = ["_opp_conf", "_opp_div"]
    played = played.join(conf_div_df)

    div_record = _count_record_schedule(played[(played["_opp_conf"] == JAX_CONF) & (played["_opp_div"] == JAX_DIV)])
    conf_record = _count_record_schedule(played[played["_opp_conf"] == JAX_CONF])
    nfc_record = _count_record_schedule(played[played["_opp_conf"] == "NFC"])
    home_record = _count_record_schedule(played[played["home"] == "Home"])
    away_record = _count_record_schedule(played[played["home"] == "Away"])
    streak = _compute_streak_schedule(played)

    div_pill = (
        f"<span class='jax-record-pill jax-record-pill-division'><span class='jax-record-label'>Division</span> <span class='jax-record-num'>{div_record}</span></span>"
        if div_record
        else ""
    )

    pills = []
    if conf_record:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Conference</span> <span class='jax-record-num'>{conf_record}</span></span>"
        )
    if nfc_record:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>NFC</span> <span class='jax-record-num'>{nfc_record}</span></span>"
        )
    if home_record:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Home</span> <span class='jax-record-num'>{home_record}</span></span>"
        )
    if away_record:
        pills.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Away</span> <span class='jax-record-num'>{away_record}</span></span>"
        )

    if streak and len(streak) > 1 and int(streak[1:]) >= 2:
        cls = "jax-record-pill jax-record-streak" + (
            " jax-record-streak-loss"
            if streak.startswith("L")
            else " jax-record-streak-draw" if streak.startswith("D") else ""
        )
        pills.append(
            f"<span class='{cls}'><span class='jax-record-label'>Streak</span> <span class='jax-record-num'>{streak}</span></span>"
        )

    return f"""
<div id="schedule-record-bar">
  <div class="jax-record-inner">
    <div class="jax-record-main"><span class="jax-record-team">JAX</span> <span class="jax-record-overall">{overall}</span> {div_pill}</div>
    <div class="jax-record-splits">{' '.join(pills)}</div>
  </div>
</div>""".strip()


def build_pc_table(df):
    html = '<div class="schedule-desktop"><table class="schedule-table"><thead><tr><th>Week</th><th>Date & Time</th><th>Opponent</th><th>Home/Away</th><th>Score</th><th>Result</th></tr></thead><tbody>'
    for _, r in df.iterrows():
        opp = (
            "BYE"
            if str(r["opponent"]).upper() == "BYE"
            else f'<span class="team-badge" style="background:{r.get("bg","#ccc")};color:{r.get("fg","#000")};">{r["opponent"]}</span>'
        )
        html += f'<tr class="{r["class"]}"><th scope="row">{r["week"]}</th><td>{r["datetime_str"]}</td><td>{opp}</td><td class="venue {r["venue_class"]}">{r["home"]}</td><td>{r["score"]}</td><td>{r["result"]}</td></tr>'
    return html + "</tbody></table></div>"


def build_mobile_table(df):
    html = '<div class="schedule-mobile"><table class="schedule-table mobile-compact"><thead><tr><th>Week</th><th>Date</th><th>Opponent</th><th>Score</th></tr></thead><tbody>'
    for _, r in df.iterrows():
        if str(r.get("opponent", "")).upper() == "BYE":
            html += f'<tr class="{r["class"]}"><td>{r["week"]}</td><td></td><td>BYE</td><td></td></tr>'
        else:
            sym = "vs" if r["venue_class"] == "home" else "@"
            res = f'<small class="result {r["class"]}">{r["result"]}</small>' if r["result"] in ["W", "L", "D"] else ""
            opp = f'<span class="venue {r["venue_class"]}">{sym}</span><span class="team-badge" style="background:{r.get("bg","#ccc")}; color:{r.get("fg","#000")};">{r["opponent"]}</span>'
            html += f'<tr class="{r["class"]}"><td>{r["week"]}</td><td>{r["date"]}<br><small>{r["time"] or "TBD"}</small></td><td>{opp}</td><td>{r["score"]}<br>{res}</td></tr>'
    return html + "</tbody></table></div>"


# ==========================================
# 2.5 新設ロジック：ヘッダー専用Snippetの生成
# ==========================================


def build_header_snippet_data(df):
    # --- スコアスライド作成 ---
    slides_html = ""
    for _, r in df.iterrows():
        if str(r["opponent"]).upper() == "BYE":
            slides_html += f"<div class='schedule-slide bye' data-date=''><div class='line1'><span class='week'>{r['week']}</span></div><div class='line2'><span class='opponent'>BYE</span></div></div>"
        else:
            sym = "vs" if r["venue_class"] == "home" else "@"
            dt_obj = r["datetime"]
            # data-dateをシンプルなISO形式（T00:00:00）に修正
            clean_date = dt_obj.strftime("%Y-%m-%dT%H:%M:%S") if not pd.isna(dt_obj) else ""
            dt_display = dt_obj.strftime("%-m/%-d (%a) %H:%M JST") if not pd.isna(dt_obj) else "TBD"
            # 結果表示のロジック修正 (- - にならないように)
            res_val = f"{r['result']} {r['score']}" if r["result"] in ["W", "L", "D"] else "-"

            slides_html += f"""<div class='schedule-slide {r['class']}' data-date='{clean_date}'><div class='line1'><span class='week'>{r['week']}</span>　{dt_display}</div><div class='line2'><span class='opponent'><span class='venue {r['venue_class']}'>{sym}</span><span class='team-badge' style='background:{r.get('bg','#ccc')};color:{r.get('fg','#000')};'>{r['opponent']}</span></span><span class='result'>{res_val}</span></div></div>"""

    score_html = f"<button class='schedule-nav schedule-prev'>◀</button><div class='schedule-carousel-viewport'><div class='schedule-carousel'>{slides_html}</div></div><button class='schedule-nav schedule-next'>▶</button>"

    # --- 戦績バー（開閉式・詳細項目付き）作成 ---
    s = df["week"].astype(str)
    reg = df[~s.str.startswith("Pre") & ~df["week"].isin(POSTSEASON_WEEKS)].copy()
    played = reg[reg["win"].isin(["Win", "Lose", "Draw"])].copy()
    overall = _count_record_schedule(played) if not played.empty else "0-0"

    conf_div_df = played["opponent"].map(lambda t: TEAM_INFO.get(str(t), (None, None))).apply(pd.Series)
    conf_div_df.columns = ["_opp_conf", "_opp_div"]
    played = played.join(conf_div_df)

    div_r = _count_record_schedule(played[(played["_opp_conf"] == JAX_CONF) & (played["_opp_div"] == JAX_DIV)])
    conf_r = _count_record_schedule(played[played["_opp_conf"] == JAX_CONF])
    nfc_r = _count_record_schedule(played[played["_opp_conf"] == "NFC"])
    home_r = _count_record_schedule(played[played["home"] == "Home"])
    away_r = _count_record_schedule(played[played["home"] == "Away"])
    streak_val = _compute_streak_schedule(played)

    div_pill = (
        f"<span class='jax-record-pill jax-record-pill-division'><span class='jax-record-label'>Div</span> <span class='jax-record-num'>{div_r}</span></span>"
        if div_r
        else ""
    )

    splits = []
    if conf_r:
        splits.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Conf</span> <span class='jax-record-num'>{conf_r}</span></span>"
        )
    if nfc_r:
        splits.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>NFC</span> <span class='jax-record-num'>{nfc_r}</span></span>"
        )
    if home_r:
        splits.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Home</span> <span class='jax-record-num'>{home_r}</span></span>"
        )
    if away_r:
        splits.append(
            f"<span class='jax-record-pill'><span class='jax-record-label'>Away</span> <span class='jax-record-num'>{away_r}</span></span>"
        )
    if streak_val:
        splits.append(
            f"<span class='jax-record-pill jax-record-streak'><span class='jax-record-label'>Streak</span> <span class='jax-record-num'>{streak_val}</span></span>"
        )

    record_html = f"""<div id="jax-record-bar" class="jax-record-collapsible"><div class="jax-record-inner"><button class="jax-record-main" type="button" aria-expanded="false"><span class="jax-record-team">JAX</span><span class="jax-record-overall">{overall}</span>{div_pill}<span class="jax-record-chevron" aria-hidden="true">▼</span></button><div class="jax-record-details"><div class="jax-record-splits">{''.join(splits)}</div></div></div></div>"""

    return f'<div id="score-data-source">{score_html}</div><div id="record-data-source">{record_html}</div>'


# ==========================================
# 3. メイン処理（API取得と更新）
# ==========================================


def fetch_from_notion():
    url = f"https://api.notion.com/v1/databases/{NOTION_SCHEDULE_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    res = requests.post(url, headers=headers, json={})
    res.raise_for_status()
    rows = []
    for page in res.json()["results"]:
        p = page["properties"]
        dt_prop = p.get("試合日時（日本時間）", {}).get("date")
        team_obj = p.get("チーム", {}).get("select")
        ha_obj = p.get("Home/Away", {}).get("select")
        win_obj = p.get("Win/Lose", {}).get("select")
        score_list = p.get("Score", {}).get("rich_text", [])
        week_list = p.get("Week", {}).get("title", [])
        rows.append(
            {
                "week": week_list[0].get("plain_text", "") if week_list else "",
                "opponent": team_obj.get("name") if team_obj else "BYE",
                "home": ha_obj.get("name") if ha_obj else "",
                "score": score_list[0].get("plain_text", "-") if score_list else "-",
                "win": win_obj.get("name") if win_obj else "",
                "試合日時（日本時間）": dt_prop["start"] if dt_prop else "",
                "sort_no": p.get("Sort No", {}).get("number") or 999,
            }
        )
    return pd.DataFrame(rows)


def update_hatena(page_id, title, content):
    url = f"https://blog.hatena.ne.jp/{HATENA_USER}/{HATENA_BLOG}/atom/page/{page_id}"
    created = datetime.datetime.now().isoformat() + "Z"
    nonce = hashlib.sha1(str(random.random()).encode()).digest()
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + HATENA_API_KEY.encode()).digest()).decode()
    wsse = f'UsernameToken Username="{HATENA_USER}", PasswordDigest="{digest}", Nonce="{base64.b64encode(nonce).decode()}", Created="{created}"'
    xml = f'<?xml version="1.0" encoding="utf-8"?><entry xmlns="http://www.w3.org/2005/Atom"><title>{title}</title><content type="text/html">{escape(content)}</content></entry>'
    requests.put(url, data=xml.encode("utf-8"), headers={"X-WSSE": wsse, "Content-Type": "application/xml"})


def main():
    try:
        print("🏈 Notionからデータを取得中...")
        df = fetch_from_notion()
        colors_df = pd.read_excel(color_path)

        # 1. 【重要】Sort No で並び替え
        df = df.sort_values("sort_no").reset_index(drop=True)

        # 2. 日時整形
        raw_dates = df["試合日時（日本時間）"].fillna("").astype(str)
        df["datetime"] = pd.to_datetime(
            raw_dates.str.replace(r"\s*\(.*\)", "", regex=True).str.strip(), errors="coerce"
        )
        if df["datetime"].dt.tz is not None:
            df["datetime"] = df["datetime"].dt.tz_localize(None)

        dt_str_list = []
        for i, row in df.iterrows():
            raw_val = str(row["試合日時（日本時間）"])
            dt_obj = row["datetime"]
            if pd.isna(dt_obj) or not raw_val or raw_val == "None":
                dt_str_list.append("TBD")
            elif "T" in raw_val or ":" in raw_val:
                dt_str_list.append(dt_obj.strftime("%Y/%m/%d %H:%M"))
            else:
                dt_str_list.append(dt_obj.strftime("%Y/%m/%d") + " TBD")
        df["datetime_str"] = dt_str_list

        # 3. その他整形
        df["result"] = df["win"].map({"Win": "W", "Lose": "L", "Draw": "D"}).fillna("-")
        df["venue_class"] = df["home"].map({"Home": "home", "Away": "away"}).fillna("")
        df["score"] = df["score"].fillna("-")
        df["class"] = df["result"].map({"W": "win", "L": "loss", "D": "draw"}).fillna("upcoming")

        future = df[(df["datetime"] > pd.Timestamp.today()) & (df["score"] == "-")]
        if not future.empty:
            df.loc[future["datetime"].idxmin(), "class"] = "next-game"

        bye_mask = df["opponent"].str.upper() == "BYE"
        df.loc[bye_mask, ["datetime_str", "score", "result"]] = ""
        df.loc[bye_mask, "class"] = "bye"

        colors_df = colors_df.rename(columns={"Team": "opponent", "Color 1": "bg", "Color 2": "fg"})
        df = pd.merge(df, colors_df, on="opponent", how="left")
        df["date"] = df["datetime"].dt.strftime("%Y/%m/%d")
        df["time"] = df["datetime"].dt.strftime("%H:%M")

        # HTML組み立て（元のロジックそのまま）
        full_html = build_schedule_record_bar(df)
        pre_df = df[df["week"].astype(str).str.startswith("Pre")]
        reg_df = df[~df["week"].astype(str).str.startswith("Pre") & ~df["week"].isin(POSTSEASON_WEEKS)]
        post_df = df[df["week"].isin(POSTSEASON_WEEKS)]

        full_html += '<div class="tab-buttons">'
        tabs = [
            ("Preseason", "PRE", "pre", pre_df),
            ("Regular Season", "RS", "reg", reg_df),
            ("Postseason", "POST", "post", post_df),
        ]
        for pc_lbl, sp_lbl, tid, d in tabs:
            if tid == "post" and d.empty:
                continue
            full_html += f'<button class="tab-btn" data-sp="{sp_lbl}" data-target="{tid}">{pc_lbl}</button>'
        full_html += "</div>"
        for tid, d in [("pre", pre_df), ("reg", reg_df), ("post", post_df)]:
            if tid == "post" and d.empty:
                continue
            full_html += f'<div class="tab-content" id="{tid}" style="display:none;">{build_pc_table(d)}{build_mobile_table(d)}</div>'

        # 魂のJavaScript
        full_html += """
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
</script>"""

        # メイン更新
        update_hatena(HATENA_SCHEDULE_PAGE_ID, "2025 Game Schedule", full_html)

        # ヘッダー用Snippet更新
        if HATENA_LATEST_SCHEDULE_PAGE_ID:
            snippet_content = build_header_snippet_data(df)
            update_hatena(HATENA_LATEST_SCHEDULE_PAGE_ID, "LATEST_DATA", snippet_content)

        print("✨ すべての更新に成功したよ、しょう！")
    except Exception as e:
        print(f"エラー発生: {e}")


if __name__ == "__main__":
    main()
