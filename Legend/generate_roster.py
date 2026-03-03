#!/usr/bin/env python3
import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path


def safe_number(val):
    try:
        return f"#{int(val)}"
    except:
        return "#--"


def feet_inch_to_cm(height_str):
    try:
        feet, inch = height_str.strip().split("-")
        cm = int(feet) * 30.48 + int(inch) * 2.54
        return round(cm)
    except:
        return None


def lbs_to_kg(weight_lbs):
    try:
        kg = float(weight_lbs) * 0.45359237
        return round(kg)
    except:
        return None


def format_cap(val):
    try:
        cap = int(float(val))
        if cap >= 1_000_000:
            return f"${cap / 1_000_000:.1f}M", cap
        elif cap >= 1_000:
            return f"${cap / 1_000:.0f}K", cap
        else:
            return f"${cap}", cap
    except:
        return "", ""


def determine_status(row):
    # Leave があれば最優先で out
    if pd.notna(row.get("Leave")):
        return "out"

    status_map = {
        "IR": "ir",
        "PUP": "pup",
        "NFI": "nfi",
        "Suspended": "susp",
        "PS": "ps",
        "Exempt/International Player": "eip",
        "Left": "out",
        "Active": "active",
    }
    return status_map.get(str(row.get("Status", "")).strip(), "active")


def generate_roster_html(roster_csv, team_color_xlsx, output_html):
    df = pd.read_csv(roster_csv)
    team_colors_df = pd.read_excel(team_color_xlsx)
    current_year = datetime.now().year

    # ポジションごとの並び順定義
    position_order = {
        "QB": 0,
        "RB": 1,
        "WR": 2,
        "TE": 3,
        "OL": 4,
        "DL": 5,
        "EDGE": 6,
        "LB": 7,
        "CB": 8,
        "S": 9,
        "K": 10,
        "P": 11,
        "LS": 12,
    }

    # 最も優先順位の高いポジション（数字が小さい）を Primary_Pos にする
    def get_primary_pos(pos_list):
        if not isinstance(pos_list, list) or not pos_list:
            return ""

        # 並び順に従ってソートし、最も若いものを返す
        sorted_pos = sorted(pos_list, key=lambda p: position_order.get(p, 999))
        return sorted_pos[0]

    # Position列をリスト化（最重要！）
    df["Position"] = df["Position"].fillna("").str.split(r",\s*")

    # 優先ポジションを取得
    df["Primary_Pos"] = df["Position"].apply(get_primary_pos)

    # 並び順番号付与
    df["Pos_Order"] = df["Primary_Pos"].map(position_order)

    # 並び替え：在籍→ポジション順→背番号順
    df["Leave_Flag"] = df["Leave"].notna().astype(int)
    df = df.sort_values(by=["Leave_Flag", "Pos_Order", "#"], ascending=[True, True, True])

    # build team → colors mapping
    team_colors = {row["Team"]: {"bg": row["Color 1"], "fg": row["Color 2"]} for _, row in team_colors_df.iterrows()}

    # career badge maps
    career_map = {
        "DRAFT": ("draft", "DRAFT"),
        "UDFA": ("udfa", "UDFA"),
        "UFA": ("fa", "FA"),
        "SFA": ("fa", "FA"),
        "WAIVER": ("waiver", "WAIVER"),
        "TRADE": ("trade", "TRADE"),
        "PS": ("psacq", "PS"),  # ← クラスは psacq, 表示は PS
    }

    # Capの整形
    def format_cap(val):
        try:
            s = str(val).strip().replace("$", "").replace(",", "")
            cap = int(float(s))
            if cap >= 1_000_000:
                return f"${cap/1_000_000:.1f}M", cap
            elif cap >= 1_000:
                return f"${cap/1_000:.0f}K", cap
            else:
                return f"${cap}", cap
        except:
            return "", 0

    # Stats 列群を定義
    stats_year = "2024"
    stats_cols = [col for col in df.columns if col.startswith("Stats -") and col.endswith(f"({stats_year})")]

    html_lines = []
    html_lines.append('<div class="roster-list">')
    html_lines.append('<ul id="rosterList" class="player-list">')

    for _, row in df.iterrows():
        # number
        if pd.notna(row.get("Leave")):
            number = ""
        else:
            number = safe_number(row["#"])

        name = row["Name"]
        college = row["College"]
        dob = row["Date Of Birth"]
        year = int(row["Entering Year"])
        draft_year = str(row.get("Entering Year", "")).strip()

        # status badge
        status = determine_status(row)
        status_html = (
            f'<span class="badge-status badge-{status}">{status.upper()}</span>'
            if status not in ("active", "out")
            else ""
        )

        # career badge if joined this year
        badge_career = ""
        if int(row.get("Joining Year", 0)) == current_year:
            js = str(row["Joining Style"]).strip().upper()
            mapping = career_map.get(js)
            if mapping:
                cls, label = mapping
                badge_career = f'<span class="badge-career badge-{cls}">{label}</span>'

        # combine badges
        badges = " ".join(filter(None, [badge_career, status_html]))
        badge_block = f'<div class="player-badges">{badges}</div>' if badges else ""

        # position/sub position
        raw_pos = row.get("Position", "")

        # 文字列でもリストでも、すべてリスト化して扱う
        if not isinstance(raw_pos, list):
            raw_pos = [p.strip().upper() for p in str(raw_pos).split(",") if p.strip()]
        else:
            raw_pos = [p.strip().upper() for p in raw_pos if p.strip()]

        # 並び順に基づいて整列
        sorted_pos = sorted(raw_pos, key=lambda p: position_order.get(p, 999))
        pos_str = "/".join(sorted_pos)

        subpos = row.get("Sub Position", "")
        if pd.notna(subpos) and subpos:
            subpos_parts = [p.strip() for p in str(subpos).split(",") if p.strip()]
            full_pos = f"{pos_str} ({'/'.join(subpos_parts)})"
        else:
            full_pos = pos_str

        # draft entry info
        if pd.notna(row.get("Draft Round")):
            entry_info = f"{int(row['Draft Round'])}R / #{int(row['Draft Overall'])}"
        else:
            entry_info = "UDFA"
        entry_team = str(row.get("Draft Team", "")).strip()
        entry_str = f"{year} / {entry_info} / {entry_team}"
        ecol = team_colors.get(entry_team, {"bg": "#006778", "fg": "#D7A22A"})
        entry_html = (
            f'<span style="background-color:{ecol["bg"]};'
            f'color:{ecol["fg"]};padding:1px 4px;border-radius:4px;">'
            f"{entry_str}</span>"
        )

        # acquired info
        acq_team = str(row.get("Former Team", "")).strip()
        acq_str = f"{int(row.get('Joining Year',0))} / {row.get('Joining Style','')}"
        if acq_team and row.get("Joining Style", "").upper() not in ["DRAFT", "UDFA"]:
            acq_str += f" / {acq_team}"
        acol = team_colors.get(acq_team, {"bg": "#006778", "fg": "#D7A22A"})
        acquired_html = (
            f'<span style="background-color:{acol["bg"]};'
            f'color:{acol["fg"]};padding:1px 4px;border-radius:4px;">'
            f"{acq_str}</span>"
        )

        # Join Year
        join_year = ""
        if pd.notna(row.get("Joining Year", None)):
            join_year = str(int(row["Joining Year"]))

        # free agency year
        try:
            fa_year = int(row.get("FA", ""))
            if fa_year == current_year + 1:
                fa_html = (
                    f'<span style="background-color:#ff4c4c;color:white;'
                    f'padding:1px 4px;border-radius:4px;font-weight:bold;">{fa_year}</span>'
                )
            else:
                fa_html = str(fa_year)
        except:
            fa_html = ""

        # Salary Cap
        cap_display, cap_value = format_cap(row.get("Salary Cap", ""))

        # Stats (2024)
        stats_items = []
        for col in stats_cols:
            raw = row.get(col, "")
            # NaN なら空文字、そうでなければ文字列化して strip()
            if pd.isna(raw) or not str(raw).strip():
                continue
            cat = col.replace("Stats -", "").replace(f"({stats_year})", "").strip(" -")
            subs = [s.strip() for s in str(raw).split(" / ")]
            sub_html = []
            for s in subs:
                if ": " in s:
                    lbl, val = s.split(": ", 1)
                    sub_html.append(f"<strong>{lbl}:</strong>&nbsp;{val}")
                else:
                    sub_html.append(s)
            inner = " / ".join(sub_html)
            stats_items.append(f'<li class="info-line"><strong>{cat}:</strong><div class="value">{inner}</div></li>')

        # 中身がなければハイフン
        if stats_items:
            stats_html = (
                f'<div class="player-stats info-block">\n'
                f"  <strong>Stats ({stats_year}):</strong>\n"
                f"  <ul>\n" + "\n".join(stats_items) + f"\n  </ul>\n"
                f"</div>\n"
            )
        else:
            stats_html = f'<div class="player-stats">' f"<strong>Stats ({stats_year}):</strong> -" f"</div>"

        # Combine
        val = row.get("Combine", "")
        if pd.isna(val) or not str(val).strip():
            combine_html = "-"
        else:
            parts = [p.strip() for p in str(val).split(" / ")]
            formatted = []
            for p in parts:
                if ": " in p:
                    lbl, v = p.split(": ", 1)
                    formatted.append(f"<strong>{lbl}:</strong>&nbsp;{v}")
                else:
                    formatted.append(p)
            combine_html = " / ".join(formatted)

        # notes (empty string if NaN)
        notes = row.get("Notes", "")
        if pd.isna(notes):
            notes = ""

        # data-number
        if pd.notna(row.get("Leave")):
            number_data = ""
        else:
            number_data = str(int(row.get("#", 0))) if pd.notna(row.get("#")) else ""

        # 加入経路を小文字で取得（例: "ufa", "sfa", "draft"）
        acq_style = str(row.get("Joining Style", "")).strip().lower()

        # 並び替え用の代表ポジション
        primary_pos = str(row.get("Primary_Pos", "")).strip().upper()

        # 検索用キーワードを結合
        search_parts = [name, college]
        data_search = " ".join(str(s).lower() for s in search_parts if s)

        # <li> のクラス判定
        # 既存: 生え抜き/外部/退団ベースのクラス
        js = str(row.get("Joining Style", "")).strip().upper()
        base_class = "player-draft" if js in ("DRAFT", "UDFA") else "player-fa"

        # ★複合クラスにする（生え抜き/外部 + ステータス）
        li_classes = [base_class, f"player-{status}"]
        li_class_attr = " ".join(li_classes)

        # height/weight
        h_cm = feet_inch_to_cm(row["Height"]) if pd.notna(row.get("Height")) else None
        w_kg = lbs_to_kg(row["Weight"]) if pd.notna(row.get("Weight")) else None
        h_disp = f"{row['Height']} ({h_cm}cm)" if h_cm else str(row.get("Height", ""))
        w_disp = f"{row['Weight']}lbs ({w_kg}kg)" if w_kg else f"{row.get('Weight','')}lbs"

        player_html = f"""    <li class="{li_class_attr}" data-name="{name}" data-pos="{pos_str}" data-primary="{primary_pos}" data-number="{number_data}" data-draft="{draft_year}" data-acq="{acq_style}" data-join-year="{join_year}" data-cap="{cap_value}" data-fa="{fa_year}" data-status="{status}" data-search="{data_search}">
      <div class="player-toggle">
        {badge_block}
        <div class="player-main">
          <span class="player-number">{number}</span>
          <span class="player-name">{name}</span> |
          <span class="player-year" data-entry="{year}">---</span> |
          <span class="player-age" data-birthday="{dob}">---</span> |
          <span class="player-college">{college}</span>
        </div>
        <div class="player-sub">
          <div class="player-position"><strong>Position:</strong> {full_pos}</div>
          <div class="player-physique"><strong>Ht/Wt:</strong> {h_disp} / {w_disp}</div>
          <div class="player-combine info-line"><strong>Combine:</strong> <div class="value">{combine_html}</div></div>
          <div class="player-entry"><strong>NFL Entry:</strong> {entry_html}</div>
          <div class="player-acquired"><strong>Acquired:</strong> {acquired_html}</div>
          <div class="player-fa"><strong>FA:</strong> {fa_html}</div>
          <div class="player-cap"><strong>Salary Cap:</strong> {cap_display}</div>
          {stats_html}
          <div class="player-notes"><strong>Notes:</strong> {notes}</div>
        </div>
      </div>
    </li>"""
        html_lines.append(player_html)

    html_lines.append("  </ul>")
    html_lines.append("</div>")

    # write out
    print("\n".join(html_lines))


if __name__ == "__main__":
    # --- parse arguments ---
    if len(sys.argv) < 2:
        print("使い方: generate_roster.py <roster.csv> [team_color.xlsx] [output.html]")
        sys.exit(1)

    roster_csv = sys.argv[1]
    # default team_color.xlsx to script directory if not provided
    if len(sys.argv) > 2:
        team_color_xlsx = sys.argv[2]
    else:
        team_color_xlsx = os.path.join(os.path.dirname(__file__), "team_color.xlsx")
    # default output HTML to same folder & base name of roster_csv
    if len(sys.argv) > 3:
        output_html = sys.argv[3]
    else:
        base = os.path.splitext(os.path.basename(roster_csv))[0]
        output_html = os.path.join(os.path.dirname(roster_csv), f"{base}.html")

    print(f"[DEBUG] スクリプト開始")
    print(f"[DEBUG] CSV 読み込み: {roster_csv}")
    print(f"[DEBUG] team_color.xlsx を読み込み: {team_color_xlsx}")
    generate_roster_html(roster_csv, team_color_xlsx, output_html)
    print(f"[DEBUG] HTML を出力: {output_html}")
