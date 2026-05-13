import requests
import json
import os
import time
from datetime import datetime

# --- 設定 ---
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

def fetch_with_retry(params, retries=3):
    for i in range(retries):
        try:
            res = requests.get(API_URL, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(2)
    return None

def get_real_count():
    unique_trains = 0
    for direction in ['UP', 'DOWN']:
        for (start, end) in SEGMENTS:
            target_sta = end if direction == 'UP' else start
            data = fetch_with_retry({'line': LINE, 'sta': target_sta})
            if data and data.get('status') == 1:
                data_key = f"{LINE}-{target_sta}"
                trains = data.get('data', {}).get(data_key, {}).get(direction, [])
                if trains and 0 < int(trains[0]['ttnt']) <= 3:
                    unique_trains += 1
    return unique_trains

def is_valid_count(count, current_hour):
    """
    檢查數據是否異常
    1. 營運時間 (06:00-01:00) 班次不應為 0
    2. 班次不應超過物理極限 (例如 50 班)
    """
    # 判斷是否為營運時間 (香港時間)
    is_operational_hours = (current_hour >= 6 or current_hour < 1)
    
    if is_operational_hours and count == 0:
        print(f"偵測到異常：營運時間內班次為 0，放棄紀錄。")
        return False
    
    if count > 50:
        print(f"偵測到異常：班次數量 ({count}) 超過合理範圍，放棄紀錄。")
        return False
        
    return True

# --- 執行 ---
try:
    now = datetime.now()
    current_hour = now.hour
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    count = get_real_count()

    # 執行異常檢查
    if not is_valid_count(count, current_hour):
        exit(0) # 正常退出但不儲存，避免污染資料庫

    # 讀取並更新 JSON
    db = {}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except:
                db = {}

    if date_str not in db:
        db[date_str] = {}
    
    db[date_str][time_str] = count

    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"[{time_str}] 成功統計到 {count} 班車。")

except Exception as e:
    print(f"嚴重錯誤: {e}")
    exit(1)
