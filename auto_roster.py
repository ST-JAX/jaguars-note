import os
import sys
import pandas as pd
import requests
import json
import html
from datetime import datetime
from requests.auth import HTTPBasicAuth

# ==============================================================================
# 0. SEASON SETTINGS (シーズンが変わったら「ここだけ」変更してください)
# ==============================================================================
CURRENT_SEASON = 2025
STATS_YEAR = str(CURRENT_SEASON - 1)
LEAVE_FILTER_YEAR = str(CURRENT_SEASON)

# リーグ切り替え設定 (3月11日)
LEAGUE_START_MONTH = 3
LEAGUE_START_DAY = 11

# ==============================================================================
# 1. 設定・定数
# ==============================================================================
NOTION_API_KEY = os.environ.get('NOTION_TOKEN') 
ROSTER_DB_ID = os.environ.get('NOTION_ROSTER_DB_ID')

HATENA_ID = os.environ.get('HATENA_USER')
HATENA_BLOG_ID = os.environ.get('HATENA_BLOG')
HATENA_API_KEY = os.environ.get('HATENA_API_KEY')
TARGET_ENTRY_ID = os.environ.get('HATENA_LATEST_ROSTER_PAGE_ID')

# 画像URLマッピング
POSITION_IMAGES = {
    "QB": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214001759.png",
    "RB": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042003.png",
    "WR": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042019.png",
    "TE": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042023.png",
    "OL": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042028.png",
    "DL": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042011.png",
    "EDGE": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042032.png",
    "LB": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042038.png",
    "CB": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042053.png",
    "S": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042048.png",
    "K": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042502.png",
    "P": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042502.png",
    "LS": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042043.png",
    "RS": "https://cdn-ak.f.st-hatena.com/images/fotolife/S/StaiL21/20251214/20251214042043.png",
}

# ★CSSを追加：Transactions用のスタイル定義
CONTROL_PANEL_HTML = """
  <div class="control-panel">
    <div class="panel-header">
      <span class="panel-title">ROSTER GUIDE & CONTROLS</span>
    </div>
    <div class="panel-body guide-area">
      <div class="guide-grid">
        <div class="guide-section">
          <div class="guide-title"><span class="icon">■</span> STATUS COLOR (Border)</div>
          <ul class="color-legend">
            <li><span class="dot active">&nbsp;</span> Active</li>
            <li><span class="dot ir">&nbsp;</span> IR / PUP / NFI</li>
            <li><span class="dot susp">&nbsp;</span> Suspended</li>
            <li><span class="dot ps">&nbsp;</span> Practice Squad</li>
            <li><span class="dot out">&nbsp;</span> Former</li>
          </ul>
        </div>
        <div class="guide-section">
          <div class="guide-title"><span class="icon">★</span> BADGES</div>
          <ul class="badge-legend">
            <li><span class="pop-badge badge-new">NEW</span> <span class="desc">Joined This Year</span></li>
            <li><span class="pop-badge badge-honor">PRO BOWL</span> <span class="desc">Honors</span></li>
          </ul>
        </div>
        <div class="guide-section full-width">
          <div class="guide-title"><span class="icon">?</span> CARD STRUCTURE (Click to Open)</div>
          <ul class="player-list" style="margin:0; width:100%; max-width:none;">
            <li class="player-card guide-sample-card" data-status="active" style="margin-bottom:0;">
              <div class="player-number">#</div>
              <span class="status-ribbon">STATUS</span>
              <div class="player-toggle">
                <div class="player-graphic-col">
                    <img src="" class="player-silhouette pos-qb" style="transform: translateX(-5%);" loading="lazy">
                </div>
                <div class="player-content-col">
                  <div class="player-header">
                    <div class="header-top">
                      <span class="player-position-label">POS</span>
                      <span class="player-name">PLAYER NAME</span>
                      <div class="pop-badge-wrapper is-new"><span class="pop-badge badge-new">BADGE</span></div>
                    </div>
                    <div class="header-sub">
                        <div class="acq-composite-badge">
                          <span class="badge-method-part">STYLE</span>
                          <span class="badge-team-part team-jax" style="background:#006778; color:#fff">TEAM</span>
                        </div>
                        <span class="meta-data">Exp Year / Age</span>
                    </div>
                  </div>
                  <div class="player-details-wrapper">
                    <div class="player-details-inner">
                      <div class="detail-grid">
                          <div class="info-item"><span class="label">Ht/Wt:</span> Height / Weight</div>
                          <div class="info-item"><span class="label">College:</span> College Name</div>
                          <div class="info-item" style="min-width: 100%;">
                            <span class="label">Entry:</span> Year / Round / Pick
                          </div>
                      </div>
                      <div class="stats-container">
                        <div class="stats-header">STATS (2024)</div>
                        <ul><li class="info-line">Season Stats Data...</li></ul>
                      </div>
                      <div class="contract-container">
                        <div class="contract-left">
                          <div class="contract-title">CONTRACT</div>
                          <div class="contract-value">$Total/Yr</div>
                          <div class="contract-cap">Cap: $Hit</div>
                        </div>
                        <div class="contract-right">
                          <div class="fa-label">FREE AGENT</div>
                          <div class="fa-year">YEAR</div>
                        </div>
                      </div>
                      <div class="transactions-container">
                        <span class="label">TRANSACTIONS</span>
                        <div class="trans-line">
                          <span class="trans-date">20XX/XX/XX</span>
                          <span class="trans-content">Transaction</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div> 
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
    <div class="panel-divider"></div>
    <div id="roster-controls" class="panel-body search-area">
      <div class="filter-container">
        <div class="control-box full">
          <label>KEYWORD SEARCH</label>
          <input id="searchInput" type="text" placeholder="# / Name / College" />
        </div>
        <div class="control-box">
          <label>FILTERS</label>
          <div class="input-row">
            <select id="filterPos">
              <option value="">Position (All)</option>
              <option value="QB">QB</option>
              <option value="RB">RB</option>
              <option value="WR">WR</option>
              <option value="TE">TE</option>
              <option value="OL">OL</option>
              <option value="DL">DL</option>
              <option value="EDGE">EDGE</option>
              <option value="LB">LB</option>
              <option value="CB">CB</option>
              <option value="S">S</option>
              <option value="K">K</option>
              <option value="P">P</option>
              <option value="LS">LS</option>
            </select>
            <select id="filterStatus">
              <option value="">Status (All)</option>
              <option value="active">Active</option>
              <option value="ir">IR / PUP / NFI</option>
              <option value="susp">Suspended</option>
              <option value="ps">Practice Squad</option>
              <option value="out">Former</option>
            </select>
          </div>
          <div class="input-row">
            <select id="filterAcq">
              <option value="">Acquired (All)</option>
              <option value="draft">Draft</option>
              <option value="udfa">UDFA</option>
              <option value="ufa">UFA</option>
              <option value="trade">Trade</option>
              <option value="waiver">Waiver</option>
            </select>
            <input id="filterDraft" type="text" placeholder="Draft" style="width:33%" />
            <input id="filterJoin" type="text" placeholder="Join" style="width:33%" />
            <input id="filterFa" type="text" placeholder="FA Year" style="width:33%" />
          </div>
        </div>
        <div class="control-box">
          <label>SORT & OPTION</label>
          <div class="input-row">
            <select id="sortBy">
              <option value="">Default Sort</option>
              <option value="number">Number</option>
              <option value="name">Name</option>
              <option value="pos">Position</option>
              <option value="cap">Cap Hit</option>
            </select>
            <button id="sortToggle" class="sort-btn" data-dir="asc" aria-label="Toggle Sort"></button>
          </div>
          <div class="option-row">
            <label class="checkbox-label" for="hideOut">
              <input id="hideOut" type="checkbox" checked /> Hide Former Players
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
"""

JS_CONTENT = """
<p>
<script>
document.addEventListener("DOMContentLoaded", function () {
  const cards = document.querySelectorAll('.player-card');
  const playerList = document.querySelector("#rosterList");

  cards.forEach(card => {
    const toggle = card.querySelector('.player-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        card.classList.toggle('is-open');
      });
    }
  });

  const searchInput = document.getElementById("searchInput");
  const filterPos = document.getElementById("filterPos");
  const filterStatus = document.getElementById("filterStatus");
  const filterAcq = document.getElementById("filterAcq");
  const filterDraft = document.getElementById("filterDraft");
  const filterJoin = document.getElementById("filterJoin");
  const filterFa = document.getElementById("filterFa");
  const sortBy = document.getElementById("sortBy");
  const sortToggle = document.getElementById("sortToggle");
  const hideOut = document.getElementById("hideOut");

  const toNum = (v, fallback = 99999) => {
    const n = parseFloat(v);
    return Number.isNaN(n) ? fallback : n;
  };

  const posPriority = { 
    QB:0, RB:1, WR:2, TE:3, OL:4, DL:5, EDGE:6, LB:7, CB:8, S:9, K:10, P:11, LS:12, RS:13, UNK:99 
  };
    
  const statusPriority = { active: 0, ir: 1, pup: 2, nfi: 3, ps: 4, susp: 5, eip: 6, out: 99 };

  const doFilterAndSort = () => {
    const searchVal = (searchInput.value || "").toLowerCase().trim();
    const posVal = filterPos.value;
    const statusVal = filterStatus.value;
    const acqVal = filterAcq.value;
    const draftVal = (filterDraft.value || "").trim();
    const joinVal = (filterJoin.value || "").trim();
    const faVal = (filterFa.value || "").trim();
    const isHideOut = hideOut.checked;

    const sortKey = sortBy.value; 
    const sortDir = sortToggle.dataset.dir === "desc" ? -1 : 1;

    const items = Array.from(playerList.children);

    const visibleItems = items.filter(item => {
      const d = item.dataset;
      if (searchVal && !d.search.includes(searchVal)) return false;
      if (posVal && d.pos !== posVal) return false;
      if (statusVal && d.status !== statusVal) return false;
      if (acqVal && d.acq !== acqVal) return false;
      if (draftVal && d.draft !== draftVal) return false;
      if (joinVal && d.join !== joinVal) return false;
      if (faVal && d.fa !== faVal) return false;
      if (isHideOut && d.status === "out") return false;
      return true;
    });

    items.forEach(item => item.style.display = "none");
    visibleItems.forEach(item => item.style.display = "");

    if (sortKey) {
      visibleItems.sort((a, b) => {
        const da = a.dataset;
        const db = b.dataset;
        if (sortKey === "number" || sortKey === "cap") {
          return (toNum(da[sortKey], 0) - toNum(db[sortKey], 0)) * sortDir;
        } else if (sortKey === "name") {
          return da.name.localeCompare(db.name) * sortDir;
        } else if (sortKey === "pos") {
          const pA = posPriority[da.pos] ?? 99;
          const pB = posPriority[db.pos] ?? 99;
          if (pA !== pB) return (pA - pB) * sortDir;
          return (toNum(da.number) - toNum(db.number));
        }
        return 0;
      });
    } else {
      visibleItems.sort((a, b) => {
        const pA = posPriority[a.dataset.pos] ?? 99;
        const pB = posPriority[b.dataset.pos] ?? 99;
        if (pA !== pB) return pA - pB;
        const sa = statusPriority[a.dataset.status] ?? 99;
        const sb = statusPriority[b.dataset.status] ?? 99;
        if (sa !== sb) return sa - sb;
        return toNum(a.dataset.number) - toNum(b.dataset.number);
      });
    }
    visibleItems.forEach(item => playerList.appendChild(item));
  };

  [searchInput, filterPos, filterStatus, filterAcq, filterDraft, filterJoin, filterFa, sortBy, hideOut].forEach(el => {
    if(el) el.addEventListener('input', doFilterAndSort);
  });

  if(sortToggle) {
    sortToggle.addEventListener('click', () => {
      const current = sortToggle.dataset.dir || "asc";
      const nextDir = current === "asc" ? "desc" : "asc";
      sortToggle.dataset.dir = nextDir;
      sortToggle.textContent = nextDir === "asc" ? "ASC" : "DESC";
      doFilterAndSort();
    });
  }

  const controlPanel = document.querySelector('.control-panel');
  if (controlPanel) {
    const header = controlPanel.querySelector('.panel-header');
    if (header) { 
        header.addEventListener('click', function() {
          if (window.innerWidth <= 600) {
            controlPanel.classList.toggle('is-panel-open');
          }
        });
    }
  }
    
  doFilterAndSort();
});
</script>
</p>
"""

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
        elif prop_type == "date":
            return prop["date"]["start"] if prop["date"] else ""
        elif prop_type == "url":
            return prop["url"] if prop["url"] else ""
        elif prop_type == "email":
            return prop["email"] if prop["email"] else ""
        elif prop_type == "checkbox":
            return prop["checkbox"]
    except:
        return ""
    return ""

def fetch_roster_data():
    url = f"https://api.notion.com/v1/databases/{ROSTER_DB_ID}/query"
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
        if next_cursor:
            payload["start_cursor"] = next_cursor
            
        resp = requests.post(url, headers=headers, json=payload)
        
        if resp.status_code != 200:
            print(f"[ERROR] Notion API Failed: {resp.text}", file=sys.stderr)
            break
            
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    data_list = []
    for page in results:
        item = {
            "Name": get_property_value(page, "Name"),
            "#": get_property_value(page, "#"),
            "Position": get_property_value(page, "Position"),
            "Sub Position": get_property_value(page, "Sub Position"),
            "Status": get_property_value(page, "Status"),
            "College": get_property_value(page, "College"),
            "Height": get_property_value(page, "Height"),
            "Weight": get_property_value(page, "Weight"),
            "Date Of Birth": get_property_value(page, "Date Of Birth"),
            "Entering Year": get_property_value(page, "Entering Year"),
            "Joining Year": get_property_value(page, "Joining Year"),
            "Joining Style": get_property_value(page, "Joining Style"),
            "Draft Team": get_property_value(page, "Draft Team"),
            "Draft Round": get_property_value(page, "Draft Round"),
            "Draft Overall": get_property_value(page, "Draft Overall"),
            "Former Team": get_property_value(page, "Former Team"),
            "Contract": get_property_value(page, "Contract"),
            "Cap Salary": get_property_value(page, "Cap Salary"),
            "FA": get_property_value(page, "FA"),
            "Honors": get_property_value(page, "Honors"),
            "Leave": get_property_value(page, "Leave"),
            # ★変更：Notes -> Transactions
            "Transactions": get_property_value(page, "Transactions")
        }
        
        props = page.get("properties", {})
        for key in props.keys():
            if key.startswith(f"Stats -"): 
                item[key] = get_property_value(page, key)
        
        if "Combine" in props:
            item["Combine"] = get_property_value(page, "Combine")

        data_list.append(item)

    df = pd.DataFrame(data_list)
    print(f"Fetched {len(df)} records.", file=sys.stderr)
    return df

def feet_to_cm(height_str):
    try:
        parts = str(height_str).split("-")
        feet = int(parts[0])
        inches = int(parts[1])
        return round(feet * 30.48 + inches * 2.54)
    except:
        return 0

def lbs_to_kg(weight_lbs):
    try:
        return round(float(weight_lbs) * 0.453592)
    except:
        return 0

def safe_number(val):
    try:
        return str(int(float(val)))
    except:
        return "00"

def format_cap(val):
    try:
        # 入力値を文字列にして、カンマや$を除去してスペース区切りにする
        s = str(val).replace("$", "").replace(",", " ").strip()
        
        # 最初の要素（今年の分）だけ取り出す
        first_val = s.split()[0]
        
        cap = int(float(first_val))
        if cap >= 1_000_000:
            return f"${cap / 1_000_000:.1f}M", cap
        elif cap >= 1_000:
            return f"${cap / 1_000:.0f}K", cap
        else:
            return f"${cap}", cap
    except:
        return "-", 0

def determine_status(row):
    leave_val = str(row.get("Leave", "")).strip()
    if leave_val and leave_val != "nan" and leave_val != "":
        return "out"
        
    s = str(row.get("Status", "")).strip().lower()
    mapping = {
        "ir": "ir", "pup": "pup", "nfi": "nfi",
        "suspended": "susp", "ps": "ps", "eip": "eip",
        "left": "out", "active": "active",
    }
    return mapping.get(s, "active")

def get_status_rank(row):
    s = str(row.get("Status", "")).strip()
    leave_val = str(row.get("Leave", "")).strip()
    if leave_val and leave_val != "nan" and leave_val != "":
        return 99

    if "Active" in s: return 0
    if "IR" in s: return 1
    if "PUP" in s: return 2
    if "NFI" in s: return 3
    if "PS" in s: return 4
    if "Suspended" in s: return 5
    if "Exempt" in s or "International" in s: return 6
    return 99

def get_team_class(team_name):
    if not team_name:
        return "team-other"
    slug = str(team_name).strip().lower()
    return f"team-{slug}"

def calc_nfl_age_exp(birth_date_str, entering_year):
    today = datetime.now()
    
    # 1. 年齢計算
    age_display = "---"
    if birth_date_str and str(birth_date_str).strip() and str(birth_date_str) != "nan":
        try:
            birth = datetime.strptime(str(birth_date_str).strip(), '%Y-%m-%d')
            years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            month_diff = (today.month - birth.month + 12) % 12
            if today.day < birth.day:
                month_diff -= 1
            age_val = years + (max(0, month_diff) / 12.0)
            age_display = f"{age_val:.1f} Yrs"
        except:
            pass

    # 2. 経験年数計算 (3月11日境界)
    league_start = datetime(today.year, LEAGUE_START_MONTH, LEAGUE_START_DAY)
    
    if today < league_start:
        calc_year = today.year - 1
    else:
        calc_year = today.year

    try:
        exp_val = calc_year - int(float(entering_year))
        exp_display = "Exp: R" if exp_val <= 0 else f"Exp: {exp_val}"
    except:
        exp_display = "-"

    return age_display, exp_display

def generate_html_content(df):
    position_order = {
        "QB": 0, "RB": 1, "WR": 2, "TE": 3, "OL": 4, 
        "DL": 5, "EDGE": 6, "LB": 7, "CB": 8, "S": 9, 
        "K": 10, "P": 11, "LS": 12, "RS": 13
    }

    df["Position"] = df["Position"].fillna("").astype(str)
    
    def get_primary(pos_val):
        raw = [p.strip().upper() for p in pos_val.split(",") if p.strip()]
        if not raw: return "UNK"
        return sorted(raw, key=lambda p: position_order.get(p, 999))[0]

    df["Primary_Pos"] = df["Position"].apply(get_primary)
    df["Pos_Order"] = df["Primary_Pos"].map(position_order)
    
    def should_keep(row):
        leave_raw = row["Leave"]
        if leave_raw == "" or leave_raw is None:
            return True
        s_val = str(leave_raw).replace(".0", "")
        if s_val == LEAVE_FILTER_YEAR:
            return True
        return False

    df = df[df.apply(should_keep, axis=1)]
    df["Status_Rank"] = df.apply(get_status_rank, axis=1)
    df = df.sort_values(by=["Pos_Order", "Status_Rank", "#"], ascending=[True, True, True])

    target_stats_str = f"({STATS_YEAR})"
    stats_cols = [c for c in df.columns if c.startswith("Stats -") and target_stats_str in c]
    
    html_lines = []
    html_lines.append('<div class="roster-wrapper">')
    html_lines.append(CONTROL_PANEL_HTML)
    html_lines.append('<ul id="rosterList" class="player-list">')

    for _, row in df.iterrows():
        name = row["Name"]
        number = safe_number(row.get("#"))
        primary_pos = row["Primary_Pos"]
        img_url = POSITION_IMAGES.get(primary_pos, POSITION_IMAGES["QB"])
        pos_class = f"pos-{primary_pos.lower()}"
        college = row["College"]
        status = determine_status(row)

        h_ft = row.get("Height", "-")
        h_cm = feet_to_cm(h_ft)
        w_lbs = row.get("Weight", "-")
        w_kg = lbs_to_kg(w_lbs)
        h_display = f"{h_ft} ({h_cm}cm)" if h_cm > 0 else str(h_ft)
        w_display = f"{w_lbs}lbs ({w_kg}kg)" if w_kg > 0 else f"{w_lbs}lbs"

        raw_pos_str = str(row.get("Position", ""))
        raw_pos_list = [p.strip().upper() for p in raw_pos_str.split(",") if p.strip()]
        sorted_pos = sorted(raw_pos_list, key=lambda p: position_order.get(p, 999))
        pos_str = "/".join(sorted_pos)

        dob = str(row.get("Date Of Birth", ""))
        entry_year = safe_number(row.get("Entering Year", 0))
        
        age_str, exp_str = calc_nfl_age_exp(dob, entry_year)

        join_style_raw = str(row.get("Joining Style", "Draft"))
        join_style = join_style_raw.upper()
        join_style_lower = join_style_raw.lower()

        join_year = safe_number(row.get("Joining Year", 0))

        former_team = str(row.get("Former Team", "")).strip()
        draft_team = str(row.get("Draft Team", "")).strip()

        badge_team_label = former_team if former_team and join_style not in ["DRAFT", "UDFA"] else draft_team
        if not badge_team_label: badge_team_label = "---"
        acq_team_class = get_team_class(badge_team_label)
        draft_team_class = get_team_class(draft_team)

        contract_raw = str(row.get("Contract", "-")).strip()
        contract_display = "-"
        if contract_raw and contract_raw != "nan" and contract_raw != "-":
             contract_display = contract_raw

        cap_val_raw = row.get("Cap Salary", 0)
        cap_disp, cap_val = format_cap(cap_val_raw)

        fa_year_raw = row.get("FA", "---")
        fa_year = str(int(float(fa_year_raw))) if str(fa_year_raw).replace('.','').isdigit() else str(fa_year_raw)
        
        is_expiring = "is-expiring" if fa_year == str(CURRENT_SEASON + 1) else ""

        stats_li = ""
        for col in stats_cols:
            raw = row.get(col, "")
            if pd.isna(raw) or not str(raw).strip(): continue
            cat = col.replace("Stats -", "").replace(target_stats_str, "").strip("- ")
            items = str(raw).split(" / ")
            fmt_items = []
            for item in items:
                if ":" in item:
                    k, v = item.split(":", 1)
                    fmt_items.append(f'<span class="stat-item"><strong>{k.strip()}:</strong> {v.strip()}</span>')
                else:
                    fmt_items.append(f'<span class="stat-item">{item.strip()}</span>')
            val_html = " / ".join(fmt_items)
            stats_li += f'<li class="info-line"><strong class="stats-category-label">{cat}:</strong><div class="value">{val_html}</div></li>'
        if not stats_li: stats_li = '<li class="info-line"><div class="value">No Stats</div></li>'

        combine_raw = str(row.get("Combine", ""))
        combine_html = "-"
        if pd.notna(combine_raw) and combine_raw.strip():
            c_items = combine_raw.split(" / ")
            fmt_c_items = []
            for c in c_items:
                if ":" in c:
                    k, v = c.split(":", 1)
                    fmt_c_items.append(f'<span class="stat-item"><strong>{k.strip()}:</strong> {v.strip()}</span>')
                else:
                    fmt_c_items.append(f'<span class="stat-item">{c.strip()}</span>')
            combine_html = " / ".join(fmt_c_items)

        # ★変更：TransactionsのHTML生成ロジック
        raw_trans = str(row.get("Transactions", "")) if pd.notna(row.get("Transactions")) else ""
        trans_items_html = ""
        
        if raw_trans.strip() and raw_trans != "nan":
            lines = raw_trans.split("\n")
            for line in lines:
                if not line.strip(): continue
                
                # "|" があれば日付と内容に分離
                if "|" in line:
                    date_part, content_part = line.split("|", 1)
                    trans_items_html += f"""
                        <div class="trans-line">
                            <span class="trans-date">{date_part.strip()}</span>
                            <span class="trans-content">{content_part.strip()}</span>
                        </div>
                    """
                else:
                    trans_items_html += f'<div class="trans-line">{line.strip()}</div>'
        else:
            trans_items_html = '<div class="trans-line no-data">No recent activity</div>'

        honors = str(row.get("Honors", "")) if pd.notna(row.get("Honors")) else ""

        badge_new_block = ""
        badge_honor_block = ""
        card_extra_class = ""
        
        if join_year == str(CURRENT_SEASON):
            card_extra_class += " is-new"
            badge_new_block = '<div class="pop-badge-wrapper is-new"><span class="pop-badge badge-new">NEW</span></div>'

        if "All-Pro" in honors:
            card_extra_class += " is-allpro"
        elif "Pro Bowl" in honors:
            card_extra_class += " is-probowl"

        honor_spans = ""
        if "All-Pro 1st" in honors:
            honor_spans += '<span class="pop-badge badge-honor">ALL-PRO 1st</span>'
        elif "All-Pro 2nd" in honors:
            honor_spans += '<span class="pop-badge badge-honor">ALL-PRO 2nd</span>'
        elif "All-Pro" in honors and "1st" not in honors and "2nd" not in honors:
            honor_spans += '<span class="pop-badge badge-honor">ALL-PRO</span>'

        if "Pro Bowl" in honors:
            honor_spans += '<span class="pop-badge badge-honor">PRO BOWL</span>'
        
        if honor_spans:
            badge_honor_block = f'<div class="pop-badge-wrapper is-honor">{honor_spans}</div>'

        draft_round = row.get("Draft Round")
        draft_year_val = ""
        if pd.notna(draft_round) and str(draft_round).strip():
            overall = safe_number(row.get("Draft Overall", 0))
            rnd = safe_number(draft_round)
            entry_str = f"{entry_year} / {rnd}R / #{overall}"
            draft_year_val = entry_year
        else:
            entry_str = f"{entry_year} / UDFA"
            if entry_year != "0": draft_year_val = entry_year

        data_search = f"{name} {college} {number} {primary_pos} {fa_year}".lower()

        # ★HTML部分修正: NotesをTransactionsに差し替え
        player_html = f"""
  <li class="player-card {card_extra_class}" 
      data-status="{status}" 
      data-name="{name}" 
      data-number="{number}" 
      data-pos="{primary_pos}" 
      data-search="{data_search}"
      data-acq="{join_style_lower}"
      data-draft="{draft_year_val}"
      data-join="{join_year}"
      data-cap="{cap_val}"
      data-fa="{fa_year}">
      
    <div class="player-number">{number}</div>
    <span class="status-ribbon">{status.upper()}</span>

    <div class="player-toggle">
      <div class="player-graphic-col">
         <img src="{img_url}" class="player-silhouette {pos_class}" loading="lazy">
      </div>
      
      <div class="player-content-col">
        <div class="player-header">
          <div class="header-top">
            <span class="player-position-label">{pos_str}</span>
            <span class="player-name">{name}</span>
            {badge_new_block}
            {badge_honor_block}
          </div>
          <div class="header-sub">
             <div class="acq-composite-badge">
               <span class="badge-method-part">{join_style} '{str(join_year)[-2:]}</span>
               <span class="badge-team-part {acq_team_class}">{badge_team_label}</span>
             </div>
             <span class="meta-data meta-exp">{exp_str}</span>
             <span class="divider">/</span>
             <span class="meta-data meta-age">{age_str}</span>
          </div>
        </div>

        <div class="player-details-wrapper">
          <div class="player-details-inner">
            <div class="detail-grid">
               <div class="info-item"><span class="label">Ht/Wt:</span> {h_display} / {w_display}</div>
               <div class="info-item"><span class="label">College:</span> {college}</div>
               <div class="info-item" style="min-width: 100%;">
                 <span class="label">Entry:</span> {entry_str} / 
                 <span class="draft-team-tag {draft_team_class}">{draft_team}</span>
               </div>
            </div>

            <div class="combine-container">
               <div class="combine-label">COMBINE</div>
               <div class="combine-data">{combine_html}</div>
            </div>
            
            <div class="stats-container">
              <div class="stats-header">STATS ({STATS_YEAR})</div>
              <ul>{stats_li}</ul>
            </div>

            <div class="contract-container">
              <div class="contract-left">
                <div class="contract-title">CONTRACT</div>
                <div class="contract-value">{contract_display}</div>
                <div class="contract-cap">Cap: {cap_disp}</div>
              </div>
              <div class="contract-right {is_expiring}">
                <div class="fa-label">FREE AGENT</div>
                <div class="fa-year">{fa_year}</div>
              </div>
            </div>
            
            <div class="transactions-container">
                <span class="label">TRANSACTIONS</span>
                {trans_items_html}
            </div>
          </div>
        </div>
      </div> 
    </div>
  </li>
"""
        html_lines.append(player_html)

    html_lines.append("</ul>")
    html_lines.append("</div>")
    html_lines.append(JS_CONTENT)
    
    return "\n".join(html_lines)

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
        title = root.find('atom:title', ns).text
        categories = [c.attrib['term'] for c in root.findall('atom:category', ns)]
        
        print(f"Current Title: {title}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Failed to get current entry: {e}", file=sys.stderr)
        return

    escaped_body = html.escape(content_body)
    escaped_title = html.escape(title)
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
        print("Successfully updated the roster page.", file=sys.stderr)
    else:
        print(f"Failed to update blog entry. Status: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)

if __name__ == "__main__":
    df = fetch_roster_data()
    html_content = generate_html_content(df)
    update_hatena_blog(html_content)
