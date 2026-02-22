import os
import sys
import json
import requests
import html
from datetime import datetime
from requests.auth import HTTPBasicAuth

# ==============================================================================
# 0. ⚙️ シーズン設定（毎年・時期によって変更する部分）
# ==============================================================================
CONFIG = {
    "CURRENT_YEAR": 2025,               # ※もしデータが2026年1年目のものなら2026にしてください
    "LEAGUE_CAP_LIMIT_MILLION": 279.2,  # リーグ基本キャップ
    "CARRYOVER_MILLION": $15.890203,           # ★追加: 前年からの繰越金や調整額（ある場合）
    "IS_TOP51_MODE": False               # True: オフシーズン(Top51), False: シーズン中(全選手)
}

# ==============================================================================
# 1. 設定・定数
# ==============================================================================
NOTION_API_KEY = os.environ.get('NOTION_TOKEN') 
CAP_DB_ID = os.environ.get('NOTION_ROSTER_DB_ID') 

HATENA_ID = os.environ.get('HATENA_USER')
HATENA_BLOG_ID = os.environ.get('HATENA_BLOG')
HATENA_API_KEY = os.environ.get('HATENA_API_KEY')

TARGET_ENTRY_ID = os.environ.get('HATENA_LATEST_CAP_PAGE_ID') or "" 

# ==============================================================================
# 2. 補助関数
# ==============================================================================
def get_property_value(page, prop_name):
    props = page.get("properties", {})
    if prop_name not in props: return ""
    
    prop = props[prop_name]
    prop_type = prop.get("type")

    try:
        if prop_type == "title":
            return prop["title"][0]["plain_text"] if prop["title"] else ""
        elif prop_type == "rich_text":
            return "".join([t["plain_text"] for t in prop["rich_text"]]) if prop["rich_text"] else ""
        elif prop_type == "number":
            return prop["number"] if prop["number"] is not None else ""
        elif prop_type == "select":
            return prop["select"]["name"] if prop["select"] else ""
        elif prop_type == "status": 
            return prop["status"]["name"] if prop["status"] else ""
        elif prop_type == "multi_select":
            return ",".join([s["name"] for s in prop["multi_select"]]) if prop["multi_select"] else ""
    except:
        return ""
    return ""

def determine_unit(positions_str):
    if not positions_str: return "Unknown"
    primary_pos = [p.strip().upper() for p in positions_str.split(",") if p.strip()][0]
    
    offense = ['QB', 'RB', 'FB', 'WR', 'TE', 'OL', 'C', 'G', 'T', 'OT', 'OG']
    defense = ['DL', 'DT', 'DE', 'NT', 'EDGE', 'LB', 'ILB', 'OLB', 'CB', 'S', 'FS', 'SS', 'DB']
    special_teams = ['K', 'P', 'LS', 'RS']
    
    if primary_pos in offense: return "Offense"
    elif primary_pos in defense: return "Defense"
    elif primary_pos in special_teams: return "Special Teams"
    return "Unknown"

def format_money(amount):
    """ドル(整数)を $○○.○M 表記に変換"""
    if not amount or amount == 0: return "$0M"
    is_negative = amount < 0
    in_millions = abs(amount) / 1000000
    formatted = f"{in_millions:.2f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return f"{'-' if is_negative else ''}${formatted}M"

# ==============================================================================
# 3. データ取得とパース
# ==============================================================================
def fetch_cap_data():
    url = f"https://api.notion.com/v1/databases/{CAP_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    results = []
    has_more = True
    next_cursor = None

    print("Fetching data from Notion...", file=sys.stderr)

    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
            
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"[ERROR] Notion API Failed: {resp.text}", file=sys.stderr)
            break
            
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    players = []
    for page in results:
        name = get_property_value(page, "Name")
        if not name: continue
        
        pos_str = get_property_value(page, "Position")
        status = get_property_value(page, "Status")
        leave_year = get_property_value(page, "Leave")
        
        unit = determine_unit(pos_str)
        
        if status == "Left":
            if leave_year == "" or float(leave_year) < (CONFIG["CURRENT_YEAR"] - 1):
                continue
            unit = "Dead"
            
        fa_val = get_property_value(page, "FA")
        fa_year = int(float(fa_val)) if str(fa_val).replace('.','').isdigit() else 2099
        
        cap_str = get_property_value(page, "Cap Salary") or "0"
        act_dead_str = get_property_value(page, "Actual Dead") or "0"
        pot_dead_str = get_property_value(page, "Potential Dead") or "0"
        
        caps = [int(float(s.strip())) if s.strip().replace('.','',1).isdigit() else 0 for s in cap_str.split(",")]
        act_deads = [int(float(s.strip())) if s.strip().replace('.','',1).isdigit() else 0 for s in act_dead_str.split(",")]
        pot_deads = [int(float(s.strip())) if s.strip().replace('.','',1).isdigit() else 0 for s in pot_dead_str.split(",")]
        
        max_len = max(len(caps), len(act_deads), len(pot_deads))
        caps += [0] * (max_len - len(caps))
        act_deads += [0] * (max_len - len(act_deads))
        pot_deads += [0] * (max_len - len(pot_deads))
        
        current_cap = caps[0]
        current_act_dead = act_deads[0]
        pot_dead = pot_deads[0]
        savings = 0 if unit == "Dead" else current_cap - pot_dead
        
        timeline_data = { (CONFIG["CURRENT_YEAR"] + i): {"cap": caps[i], "act": act_deads[i], "pot": pot_deads[i]} for i in range(max_len) }
        
        auto_pot_year = None
        for i in range(len(caps)):
            y = CONFIG["CURRENT_YEAR"] + i
            c = caps[i]
            d = pot_deads[i] if i < len(pot_deads) else 0
            savings_i = c - d
            if y >= fa_year or unit == "Dead": break
            
            if savings_i > 0 and c > 0 and savings_i >= d:
                auto_pot_year = y
                break

        primary_pos = [p.strip() for p in pos_str.split(",")][0] if pos_str else "UNK"

        players.append({
            "id": page["id"],
            "name": name,
            "position": primary_pos,
            "unit": unit,
            "faYear": fa_year,
            "currentCap": current_cap,
            "currentActualDead": current_act_dead,
            "potentialDead": pot_dead,
            "savings": savings,
            "timelineData": timeline_data,
            "contractLength": max_len,
            "potentialOutYear": auto_pot_year
        })
        
    print(f"Fetched {len(players)} active/dead records.", file=sys.stderr)
    return players

# ==============================================================================
# 4. HTMLの生成
# ==============================================================================
def generate_html_content(players, config):
    curr_year = config["CURRENT_YEAR"]
    total_cap_limit_million = config["LEAGUE_CAP_LIMIT_MILLION"] + config.get("CARRYOVER_MILLION", 0.0)
    cap_limit = int(total_cap_limit_million * 1000000)
    is_top51 = config["IS_TOP51_MODE"]
    
    active_players = [p for p in players if p["unit"] != "Dead"]
    active_players.sort(key=lambda x: x["currentCap"], reverse=True)
    
    top51_ids = [p["id"] for p in active_players[:51]]
    
    total_cap = 0
    total_act_dead = 0
    countable_players = []
    
    for p in players:
        total_act_dead += p["currentActualDead"]
        if p["unit"] != "Dead":
            if not is_top51 or p["id"] in top51_ids:
                total_cap += p["currentCap"]
                countable_players.append(p)
                
    team_total = total_cap + total_act_dead
    cap_space = cap_limit - team_total
    
    off_cap = sum(p["currentCap"] for p in countable_players if p["unit"] == "Offense")
    def_cap = sum(p["currentCap"] for p in countable_players if p["unit"] == "Defense")
    st_cap = sum(p["currentCap"] for p in countable_players if p["unit"] == "Special Teams")
    
    off_pct = (off_cap / team_total * 100) if team_total > 0 else 0
    def_pct = (def_cap / team_total * 100) if team_total > 0 else 0
    st_pct = (st_cap / team_total * 100) if team_total > 0 else 0
    dead_pct = (total_act_dead / team_total * 100) if team_total > 0 else 0
    
    pos_dict = {}
    for p in countable_players:
        pos_name = "ST" if p["unit"] == "Special Teams" else p["position"]
        pos_dict[pos_name] = pos_dict.get(pos_name, 0) + p["currentCap"]
        
    fixed_pos_order = ["QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "CB", "S", "ST"]
    pos_stats = []
    for pos in fixed_pos_order:
        if pos in pos_dict:
            pos_stats.append({"pos": pos, "cap": pos_dict[pos], "pct": (pos_dict[pos] / total_cap * 100) if total_cap > 0 else 0})
            del pos_dict[pos]
    for pos, cap in sorted(pos_dict.items(), key=lambda x: x[1], reverse=True):
        pos_stats.append({"pos": pos, "cap": cap, "pct": (cap / total_cap * 100) if total_cap > 0 else 0})

    top_caps = sorted(active_players, key=lambda x: x["currentCap"], reverse=True)[:5]
    top_pots = sorted(active_players, key=lambda x: x["potentialDead"], reverse=True)[:5]
    top_saves = sorted(active_players, key=lambda x: x["savings"], reverse=True)[:5]
    top_deads = sorted([p for p in players if p["unit"] == "Dead"], key=lambda x: x["currentActualDead"], reverse=True)[:5]
    
    max_savings = max([p["savings"] for p in active_players]) if active_players else 0

    html_lines = []
    html_lines.append('<div class="cap-dashboard-wrapper">')
    
    html_lines.append(f"""
    <div class="cap-header">
        <div class="cap-header-titles">
            <span class="cap-subtitle"><strong>【{curr_year}シーズン】</strong> 現在のキャップ状況・確定デッドマネー・契約見通し</span>
        </div>
        <div class="cap-header-stats">
            <div class="cap-mode-badge">{'Top 51 モード適用中' if is_top51 else '全選手(シーズン中)モード'}</div>
            <div class="cap-limit-info">League Cap: {format_money(cap_limit)}</div>
            <div class="cap-space-info {'space-ok' if cap_space >= 0 else 'space-ng'}">
                Remaining: {format_money(cap_space)}
            </div>
        </div>
    </div>
    """)
    
    html_lines.append(f"""
    <div class="cap-summary-grid">
        <div class="cap-summary-card">
            <div class="card-label">Active Cap Hit</div>
            <div class="card-value">{format_money(total_cap)}</div>
        </div>
        <div class="cap-summary-card dead-card">
            <div class="card-label">Actual Dead Money</div>
            <div class="card-value">{format_money(total_act_dead)}</div>
        </div>
        <div class="cap-summary-card save-card">
            <div class="card-label">Max Potential Savings</div>
            <div class="card-value">{format_money(max_savings)}</div>
        </div>
    </div>
    """)
    
    def build_ranking_html(title, items, val_key, val_class):
        lines = [f'<div class="cap-ranking-box"><h4>{title}</h4><ul class="cap-ranking-list">']
        if not items:
            lines.append('<li class="cap-ranking-empty">データなし</li>')
        for i, item in enumerate(items):
            val = item[val_key]
            lines.append(f"""
            <li class="cap-ranking-item">
                <span class="rank-num">{i+1}</span>
                <span class="rank-name">{html.escape(item['name'])}</span>
                <span class="rank-val {val_class}">{format_money(val)}</span>
            </li>
            """)
        lines.append('</ul></div>')
        return "".join(lines)

    html_lines.append('<div class="cap-ranking-grid">')
    html_lines.append(build_ranking_html("Cap Hit TOP5", top_caps, "currentCap", "val-cap"))
    html_lines.append(build_ranking_html("Untouchable (Dead) TOP5", top_pots, "potentialDead", "val-dead"))
    html_lines.append(build_ranking_html("Cut Candidates (Save) TOP5", top_saves, "savings", "val-save"))
    html_lines.append(build_ranking_html("Actual Dead TOP5", top_deads, "currentActualDead", "val-actual-dead"))
    html_lines.append('</div>')
    
    html_lines.append('<div class="cap-charts-grid">')
    html_lines.append(f"""
    <div class="cap-chart-box">
        <h4>Unit Allocation</h4>
        <div class="cap-chart-bar">
            <div class="cap-segment seg-off" style="width: {off_pct}%;">{'%.1f%%' % off_pct if off_pct > 10 else ''}</div>
            <div class="cap-segment seg-def" style="width: {def_pct}%;">{'%.1f%%' % def_pct if def_pct > 10 else ''}</div>
            <div class="cap-segment seg-st" style="width: {st_pct}%;">{'%.1f%%' % st_pct if st_pct > 10 else ''}</div>
            <div class="cap-segment seg-dead" style="width: {dead_pct}%;">{'%.1f%%' % dead_pct if dead_pct > 5 else ''}</div>
        </div>
        <div class="cap-chart-legend">
            <span class="legend-item"><span class="dot dot-off"></span>Offense</span>
            <span class="legend-item"><span class="dot dot-def"></span>Defense</span>
            <span class="legend-item"><span class="dot dot-st"></span>ST</span>
            <span class="legend-item"><span class="dot dot-dead"></span>Dead</span>
        </div>
    </div>
    """)
    
    pos_html = ""
    pos_legend = ""
    for i, st in enumerate(pos_stats):
        color_class = f"pos-color-{i % 8 + 1}"
        pos_html += f'<div class="cap-segment {color_class}" style="width: {st["pct"]}%;" title="{st["pos"]}: {format_money(st["cap"])}"></div>'
        pos_legend += f'<span class="legend-item"><span class="dot {color_class}"></span>{st["pos"]} <small>{st["pct"]:.0f}%</small></span>'
        
    html_lines.append(f"""
    <div class="cap-chart-box">
        <h4>Position Allocation</h4>
        <div class="cap-chart-bar">{pos_html}</div>
        <div class="cap-chart-legend grid-legend">{pos_legend}</div>
    </div>
    """)
    html_lines.append('</div>')
    
    timeline_players = sorted(active_players, key=lambda x: x["currentCap"], reverse=True)[:15]
    if timeline_players:
        max_t_years = max([p["contractLength"] for p in timeline_players] + [5])
        t_years = [curr_year + i for i in range(max_t_years)]
        
        html_lines.append('<div class="cap-timeline-section">')
        html_lines.append('<h4>Core Players Timeline</h4>')
        html_lines.append('<p class="cap-note">※チーム負担額上位15名のみ表示</p>')
        html_lines.append('<div class="cap-table-scroll"><div class="cap-timeline-inner">')
        
        html_lines.append('<div class="tl-header-row"><div class="tl-name-col">Player</div><div class="tl-years-col">')
        for y in t_years: html_lines.append(f'<div class="tl-year">{y}</div>')
        html_lines.append('</div></div>')
        
        for tp in timeline_players:
            dot_class = "dot-off" if tp["unit"] == "Offense" else "dot-def" if tp["unit"] == "Defense" else "dot-st"
            html_lines.append(f'<div class="tl-row"><div class="tl-name-col"><span class="dot {dot_class}"></span>{html.escape(tp["name"])}</div><div class="tl-years-col">')
            
            for y in t_years:
                is_fa_year_or_later = (tp["unit"] != "Dead" and y >= tp["faYear"])
                is_fa_exact = (tp["unit"] != "Dead" and y == tp["faYear"])
                is_pot_cut = (y == tp["potentialOutYear"])
                
                c_data = tp["timelineData"].get(y, {"cap": 0, "act": 0, "pot": 0})
                
                amount = c_data["cap"] + c_data["act"]
                
                is_void_burst = False
                if is_fa_year_or_later and amount == 0 and c_data["pot"] > 0:
                    amount = c_data["pot"]
                    is_void_burst = True
                
                is_void = is_fa_year_or_later and amount > 0
                
                cell_classes = ["tl-cell"]
                if amount > 0:
                    bg = "bg-dead" if tp["unit"] == "Dead" else "bg-void" if is_void else "bg-off" if tp["unit"] == "Offense" else "bg-def" if tp["unit"] == "Defense" else "bg-st"
                    cell_classes.append(bg)
                    
                html_lines.append(f'<div class="{" ".join(cell_classes)}">')
                if amount > 0:
                    txt_cls = "txt-void" if (is_void and tp["unit"] != "Dead") else "txt-val"
                    html_lines.append(f'<span class="{txt_cls}">{format_money(amount)}</span>')
                    if is_void and tp["unit"] != "Dead": html_lines.append('<span class="badge-void">VOID</span>')
                
                if is_pot_cut: html_lines.append('<span class="badge-pot">✂️</span>')
                if is_fa_exact and amount == 0: html_lines.append('<span class="badge-fa">FA</span>')
                html_lines.append('</div>')
                
            html_lines.append('</div></div>')
            
        html_lines.append('</div></div></div>')
    
    html_lines.append('<div class="cap-table-section">')
    html_lines.append('<div class="cap-table-header">')
    html_lines.append('<h4>Active Roster Details</h4>')
    html_lines.append('<input type="text" id="capSearchInput" placeholder="選手名・Posで検索...">')
    html_lines.append('</div>')
    
    html_lines.append('<div class="cap-table-scroll">')
    html_lines.append('<table id="capTable" class="cap-roster-table">')
    html_lines.append("""
        <thead>
            <tr>
                <th>Rk</th>
                <th>Name</th>
                <th>Pos</th>
                <th class="sortable" data-sort="cap">Cap Hit ↕</th>
                <th class="sortable" data-sort="dead">Dead(Pot) ↕</th>
                <th class="sortable" data-sort="save">Savings ↕</th>
            </tr>
        </thead>
        <tbody>
    """)
    
    # ★修正: ループ内で、21件目以降は初期状態で display: none を指定
    for i, p in enumerate(active_players):
        is_counted = not is_top51 or (p["id"] in top51_ids)
        row_cls = "" if is_counted else "not-counted"
        save_cls = "text-save" if p["savings"] > 0 else "text-danger"
        display_style = 'style="display: none;"' if i >= 20 else ''
        
        search_txt = f"{p['name']} {p['position']}".lower()
        html_lines.append(f"""
            <tr class="cap-roster-row {row_cls}" data-search="{html.escape(search_txt)}" data-cap="{p['currentCap']}" data-dead="{p['potentialDead']}" data-save="{p['savings']}" {display_style}>
                <td class="td-rk">{i+1}</td>
                <td class="td-name">{html.escape(p['name'])} {'<span class="badge-out">枠外</span>' if not is_counted else ''}</td>
                <td class="td-pos"><span class="pos-tag">{p['position']}</span></td>
                <td class="td-val {'' if is_counted else 'strike'}">{format_money(p['currentCap'])}</td>
                <td class="td-val text-muted">{format_money(p['potentialDead'])}</td>
                <td class="td-val {save_cls}">{format_money(p['savings'])}</td>
            </tr>
        """)
        
    html_lines.append('</tbody></table></div>')
    
    # ★修正: さらに表示ボタンを追加
    if len(active_players) > 20:
        html_lines.append('<div class="cap-load-more-container" style="text-align: center; padding: 1rem;">')
        html_lines.append('<button id="capLoadMoreBtn" class="cap-btn-load-more">さらに表示</button>')
        html_lines.append('</div>')
        
    html_lines.append('</div>')
    html_lines.append('</div>') # end of wrapper
    
    # ★修正: JS内に表示件数制御とボタンクリックイベントを追加
    js_content = """
    <p>
    <script>
    document.addEventListener("DOMContentLoaded", function () {
        const searchInput = document.getElementById("capSearchInput");
        const tableBody = document.querySelector("#capTable tbody");
        const loadMoreBtn = document.getElementById("capLoadMoreBtn");
        if(!tableBody) return;
        
        const rows = Array.from(tableBody.querySelectorAll(".cap-roster-row"));
        const headers = document.querySelectorAll("#capTable th.sortable");
        
        let sortCol = "cap";
        let sortDir = -1; 
        let visibleCount = 20;
        let currentQuery = "";

        function renderTable() {
            const query = (searchInput.value || "").toLowerCase().trim();
            
            // 検索内容が変わったら表示件数をリセット
            if (query !== currentQuery) {
                visibleCount = 20;
                currentQuery = query;
            }
            
            const visibleRows = rows.filter(row => {
                if (!query) return true;
                return row.dataset.search.includes(query);
            });
            
            visibleRows.sort((a, b) => {
                const valA = parseFloat(a.dataset[sortCol]) || 0;
                const valB = parseFloat(b.dataset[sortCol]) || 0;
                return (valA - valB) * sortDir;
            });
            
            // 一旦すべて非表示
            rows.forEach(r => r.style.display = "none");
            
            // visibleCount の数だけ表示してDOMに追加
            const rowsToShow = visibleRows.slice(0, visibleCount);
            rowsToShow.forEach(r => {
                r.style.display = "";
                tableBody.appendChild(r);
            });
            
            // もっと見るボタンの表示/非表示制御
            if (loadMoreBtn) {
                if (visibleCount < visibleRows.length) {
                    loadMoreBtn.style.display = "inline-block";
                } else {
                    loadMoreBtn.style.display = "none";
                }
            }
        }

        if(searchInput) {
            searchInput.addEventListener("input", renderTable);
        }
        
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener("click", () => {
                visibleCount += 20;
                renderTable();
            });
        }

        headers.forEach(th => {
            th.addEventListener("click", () => {
                const col = th.dataset.sort;
                if (sortCol === col) {
                    sortDir *= -1;
                } else {
                    sortCol = col;
                    sortDir = -1;
                }
                renderTable();
            });
        });
        
        // 初期描画時にボタンの表示判定を走らせる
        renderTable();
    });
    </script>
    </p>
    """
    
    html_lines.append(js_content)
    return "\n".join(html_lines)

# ==============================================================================
# 5. はてなブログ更新
# ==============================================================================
def update_hatena_blog(content_body):
    if not TARGET_ENTRY_ID:
        print("[ERROR] TARGET_ENTRY_ID is missing.", file=sys.stderr)
        return

    url = f'https://blog.hatena.ne.jp/{HATENA_ID}/{HATENA_BLOG_ID}/atom/page/{TARGET_ENTRY_ID}'
    
    print(f"Fetching current entry info from {url}...", file=sys.stderr)
    try:
        get_resp = requests.get(url, auth=HTTPBasicAuth(HATENA_ID, HATENA_API_KEY))
        get_resp.raise_for_status()
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_resp.text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        categories = [c.attrib['term'] for c in root.findall('atom:category', ns)]
    except Exception as e:
        print(f"[ERROR] Failed to get current entry: {e}", file=sys.stderr)
        return

    curr_year = CONFIG["CURRENT_YEAR"]
    new_title = f"SALARY CAP // {curr_year}"

    escaped_body = html.escape(content_body)
    escaped_title = html.escape(new_title)
    categories_xml = "\n".join([f'<category term="{html.escape(c)}" />' for c in categories])
    
    xml_data = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:app="http://www.w3.org/2007/app">
  <title>{escaped_title}</title>
  {categories_xml}
  <content type="text/html">{escaped_body}</content>
  <app:control>
    <app:draft>no</app:draft>
  </app:control>
</entry>
"""

    headers = {'Content-Type': 'application/atom+xml'}
    response = requests.put(
        url,
        data=xml_data.encode('utf-8'),
        headers=headers,
        auth=HTTPBasicAuth(HATENA_ID, HATENA_API_KEY)
    )

    if response.status_code == 200:
        print("Successfully updated the Cap Dashboard page.", file=sys.stderr)
    else:
        print(f"Failed to update blog entry. Status: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)

if __name__ == "__main__":
    players_data = fetch_cap_data()
    html_content = generate_html_content(players_data, CONFIG)
    update_hatena_blog(html_content)
