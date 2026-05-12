import requests
import json
import os
from datetime import datetime

# --- 設定路徑 ---
# 取得目前這個 tracker.py 檔案所在的資料夾路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "daily_stats.json")

LINE = "TWL"
SEGMENTS = [
    ("CEN", "ADM"), ("ADM", "TST"), ("TST", "JOR"), ("JOR", "YMT"),
    ("YMT", "MOK"), ("MOK", "PRE"), ("PRE", "SSP"), ("SSP", "CSW"),
    ("CSW", "LCK"), ("LCK", "MEF"), ("MEF", "LAK"), ("LAK", "KWF"),
    ("KWF", "KWH"), ("KWH", "TWH"), ("TWH", "TSW")
]
API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"

def get_real_count():
    unique_trains = 0
    for direction in ['UP', 'DOWN']:
        for (start, end) in SEGMENTS:
            target_sta = end if direction == 'UP' else start
            try:
                res = requests.get(API_URL, params={'line': LINE, 'sta': target_sta}, timeout=15).json()
                if res.get('status') == 1:
                    data_key = f"{LINE}-{target_sta}"
                    trains = res.get('data', {}).get(data_key, {}).get(direction, [])
                    if trains and 0 < int(trains[0]['ttnt']) <= 3:
                        unique_trains += 1
            except Exception as e:
                print(f"抓取 {target_sta} 失敗: {e}")
                continue
    return unique_trains

# 執行邏輯
try:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    current_count = get_real_count()

    # 讀取現有資料
    data = {}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                data = {}

    # 寫入數據
    if date_str not in data:
        data[date_str] = {}
    data[date_str][time_str] = current_count

    # 儲存
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"成功更新！偵測到 {current_count} 班車。檔案位置: {STATS_FILE}")

except Exception as e:
    print(f"程式執行發生錯誤: {e}")
    exit(1) # 強制報錯讓 GitHub Actions 知道失敗了
