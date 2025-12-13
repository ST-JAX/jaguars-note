import os
import re
import json
import csv
import time
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- Config ---
BASE_URL = "https://www.pro-football-reference.com"
ID_FILE = "pfr_ids.json"
CSV_FILE = "players.csv"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


# --- ID map persistence ---
def load_id_map():
    if os.path.exists(ID_FILE):
        return json.load(open(ID_FILE, "r", encoding="utf-8"))
    return {}


def save_id_map(m):
    with open(ID_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)


# --- Resolve PFR ID by name ---
def resolve_player_id(name, id_map):
    if name in id_map:
        return id_map[name]
    while True:
        pid = input(f"{name} の PFR ID が未登録です。IDを入力、空Enterでスキップ: ").strip()
        if not pid:
            id_map[name] = None
            break
        if ID_PATTERN.fullmatch(pid):
            id_map[name] = pid
            break
        print("有効な英数字のIDを入力してください。例: LawrTr00")
    save_id_map(id_map)
    return id_map[name]


# --- Fetch and parse ---
def fetch_soup(pid):
    url = f"{BASE_URL}/players/{pid[0]}/{pid}.htm"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280x800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        time.sleep(3)
        html = driver.page_source
        return BeautifulSoup(html, "html.parser")
    finally:
        driver.quit()


# --- Helper to extract cell text by data-stat ---
def get_cell(tr, stat):
    if not tr:
        return ""
    td = tr.find(lambda tag: tag.name in ("td", "th") and tag.get("data-stat") == stat)
    return td.get_text(strip=True) if td else ""


# --- Summary functions ---
def summary_general(soup, year):
    tr = soup.find("tr", id=f"snap_counts.{year}")
    if not tr:
        return f"[{year} のGeneralデータなし]"

    # 各セルを文字列で取り出す
    g = get_cell(tr, "g")
    gs = get_cell(tr, "gs")
    off_pct = get_cell(tr, "off_pct")
    def_pct = get_cell(tr, "def_pct")
    st_pct = get_cell(tr, "st_pct")

    parts = [
        f"GP: {g}",
        f"GS: {gs}",
    ]
    # OFF があれば OFF、なければ DEF
    if off_pct and off_pct != "0%":
        parts.append(f"OFF SNAP%: {off_pct}")
    elif def_pct and def_pct != "0%":
        parts.append(f"DEF SNAP%: {def_pct}")
    # ST は常に
    parts.append(f"ST SNAP%: {st_pct}")

    return " / ".join(parts)


def summary_passing(soup, year):
    tr = soup.find("tr", id=f"passing.{year}")
    if not tr:
        return f"[{year} のPassingデータなし]"
    return (
        f"CMP%: {get_cell(tr,'pass_cmp_pct')} / "
        f"YDS: {get_cell(tr,'pass_yds')} / "
        f"TD: {get_cell(tr,'pass_td')} / "
        f"INT: {get_cell(tr,'pass_int')} / "
        f"RATE: {get_cell(tr,'pass_rating')} / "
        f"SACK: {get_cell(tr,'pass_sacked')}"
    )


def summary_rushing(soup, year):
    tr = soup.find("tr", id=f"rushing_and_receiving.{year}") or soup.find("tr", id=f"receiving_and_rushing.{year}")
    if not tr:
        return f"[{year} のRushingデータなし]"
    return (
        f"ATT: {get_cell(tr,'rush_att')} / "
        f"YDS: {get_cell(tr,'rush_yds')} / "
        f"AVG: {get_cell(tr,'rush_yds_per_att')} / "
        f"TD: {get_cell(tr,'rush_td')} / "
        f"FUM: {get_cell(tr,'fumbles')}"
    )


def summary_receiving(soup, year):
    tr = soup.find("tr", id=f"receiving_and_rushing.{year}") or soup.find("tr", id=f"rushing_and_receiving.{year}")
    tr_adv = soup.find("tr", id=f"adv_rushing_and_receiving.{year}") or soup.find(
        "tr", id=f"adv_receiving_and_rushing.{year}"
    )
    if not tr and not tr_adv:
        return f"[{year} のReceivingデータなし]"
    return (
        f"REC: {get_cell(tr, 'rec')} / "
        f"YDS: {get_cell(tr, 'rec_yds')} / "
        f"AVG: {get_cell(tr, 'rec_yds_per_rec')} / "
        f"TD: {get_cell(tr, 'rec_td')} / "
        f"YAC: {get_cell(tr_adv, 'rec_yac')}"
    )


def summary_tackles(soup, year):
    tr_def = soup.find("tr", id=f"defense.{year}")
    tr_adv = soup.find("tr", id=f"adv_defense.{year}")
    if not tr_def and not tr_adv:
        return f"[{year} のTacklesデータなし]"
    return (
        f"SOLO: {get_cell(tr_def,'tackles_solo')} / "
        f"AST: {get_cell(tr_def,'tackles_assists')} / "
        f"MTKL%: {get_cell(tr_adv,'tackles_missed_pct')} / "
        f"TFL: {get_cell(tr_def,'tackles_loss')} / "
        f"FF: {get_cell(tr_def,'fumbles_forced')} / "
        f"FR: {get_cell(tr_def,'fumbles_rec')}"
    )


def summary_pass_rush(soup, year):
    tr = soup.find("tr", id=f"adv_defense.{year}")
    if not tr:
        return f"[{year} のPass Rushデータなし]"
    return (
        f"PRSS: {get_cell(tr,'pressures')} / "
        f"HRRY: {get_cell(tr,'qb_hurry')} / "
        f"QBKD: {get_cell(tr,'qb_knockdown')} / "
        f"SACK: {get_cell(tr,'sacks')}"
    )


def summary_coverage(soup, year):
    tr_adv = soup.find("tr", id=f"adv_defense.{year}")
    tr_def = soup.find("tr", id=f"defense.{year}")
    if not tr_adv and not tr_def:
        return f"[{year} のCoverageデータなし]"
    return (
        f"TGT: {get_cell(tr_adv,'def_targets')} / "
        f"COMP: {get_cell(tr_adv,'def_cmp')} / "
        f"YDS: {get_cell(tr_adv,'def_cmp_yds')} / "
        f"TD: {get_cell(tr_adv,'def_cmp_td')} / "
        f"INT: {get_cell(tr_def,'def_int')} / "
        f"PD: {get_cell(tr_def,'pass_defended')} / "
        f"RATE: {get_cell(tr_adv,'def_pass_rating')}"
    )


def summary_kicking(soup, year):
    tr = soup.find("tr", id=f"kicking.{year}")
    if not tr:
        return f"[{year} のKickingデータなし]"
    return (
        f"FGA: {get_cell(tr,'fga')} / "
        f"FGM: {get_cell(tr,'fgm')} / "
        f"FG%: {get_cell(tr,'fg_pct')} / "
        f"LNG: {get_cell(tr,'fg_long')} / "
        f"XPA: {get_cell(tr,'xpa')} / "
        f"XPM: {get_cell(tr,'xpm')} / "
        f"XP%: {get_cell(tr,'xp_pct')}"
    )


def summary_punting(soup, year):
    tr = soup.find("tr", id=f"punting.{year}")
    if not tr:
        return f"[{year} のPuntingデータなし]"
    return (
        f"PNT: {get_cell(tr,'punt')} / "
        f"Y/P: {get_cell(tr,'punt_yds_per_punt')} / "
        f"NY/P: {get_cell(tr,'punt_net_yds_per_punt')} / "
        f"LNG: {get_cell(tr,'punt_long')} / "
        f"TB%: {get_cell(tr,'punt_tb_pct')} / "
        f"IN20%: {get_cell(tr,'punt_in_20_pct')}"
    )


def summary_k_p_return(soup, year):
    tr = soup.find("tr", id=f"returns.{year}")
    if not tr:
        return f"[{year} のReturnデータなし]"
    return (
        f"KR: {get_cell(tr,'kick_ret')} / "
        f"KRYDS: {get_cell(tr,'kick_ret_yds')} / "
        f"Y/KR: {get_cell(tr,'kick_ret_yds_per_ret')} / "
        f"KRTD: {get_cell(tr,'kick_ret_td')} / "
        f"PR: {get_cell(tr,'punt_ret')} / "
        f"PRYDS: {get_cell(tr,'punt_ret_yds')} / "
        f"Y/PR: {get_cell(tr,'punt_ret_yds_per_ret')} / "
        f"PRTD: {get_cell(tr,'punt_ret_td')}"
    )


# Map categories to functions
CATEGORY_FUNCS = {
    "general": summary_general,
    "pass": summary_passing,
    "rush": summary_rushing,
    "recv": summary_receiving,
    "tkl": summary_tackles,
    "prs": summary_pass_rush,
    "cvg": summary_coverage,
    "k": summary_kicking,
    "p": summary_punting,
    "ret": summary_k_p_return,
}


# --- Main processing ---
def process_csv():
    id_map = load_id_map()
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            name = rec.get("name")
            year = int(rec.get("year", 0))
            pid = resolve_player_id(name, id_map)
            if not pid:
                print(f"[skip] {name}")
                continue
            print(f"\n{name} ({year})")
            soup = fetch_soup(pid)
            print("Stats (General)")
            print(summary_general(soup, year))
            for ck in rec.get("category", "").split(","):
                key = ck.strip().lower()
                func = CATEGORY_FUNCS.get(key)
                print(f"[debug] Processing: {key}")
                if func:
                    print(func(soup, year))
                else:
                    print("[未実装] get_formatted_stats の利用検討")


if __name__ == "__main__":
    process_csv()
