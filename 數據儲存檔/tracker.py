import requests
import json
import os
import time
from datetime import datetime

# --- 路徑處理 ---
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
    """帶重試機制的 API 請求"""
    for i in range(retries):
        try:
            res = requests.get(API_URL, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"第 {i+1} 次嘗試失敗: {e}")
            time.sleep(2) # 等待 2 秒後重試
    return None

def get_real_count():
    unique_trains = 0
    # 記錄已偵測到的列車，防止雙向統計時的極端重複（雖然區間法已大幅減少重複）
    for direction in ['UP', 'DOWN']:
        for (start, end) in SEGMENTS:
            target_sta = end if direction == 'UP' else start
            data = fetch_with_retry({'line': LINE, 'sta': target_sta})
            
            if data and data.get('status') == 1:
                data_key = f"{LINE}-{target_sta}"
                trains = data.get('data', {}).get(data_key, {}).get(direction, [])
                # 判定邏輯：只要該區間第一班車 ttnt 在 3 分鐘內，視為有一班車在區間內
                if trains and 0 < int(trains[0]['ttnt']) <= 3:
                    unique_trains += 1
    return unique_trains

# --- 主程式執行 ---
try:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    count = get_real_count()

    # 讀取並更新 JSON
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except:
                db = {}
    else:
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
