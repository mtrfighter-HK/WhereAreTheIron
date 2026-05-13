import requests
import json
import os
import time
from datetime import datetime
import line_config  # 導入剛才建立的設定檔

# --- 設定與路徑 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "daily_stats.json")
API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"

# 你想統計哪些路線？只需在此清單加入代碼
TARGET_LINES = ["TWL"]

def fetch_with_retry(params, retries=3):
    """帶重試機制的 API 請求"""
    for i in range(retries):
        try:
            res = requests.get(API_URL, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(2)
    return None

def get_line_train_count(line_code):
    """統計單一條路線的在線列車數"""
    unique_trains = 0
    segments = line_config.get_segments(line_code)
    
    for direction in ['UP', 'DOWN']:
        for (start, end) in segments:
            # 往荃灣 (UP) 看後方車站，往中環 (DOWN) 看前方車站
            target_sta = end if direction == 'UP' else start
            data = fetch_with_retry({'line': line_code, 'sta': target_sta})
            
            if data and data.get('status') == 1:
                data_key = f"{line_code}-{target_sta}"
                trains = data.get('data', {}).get(data_key, {}).get(direction, [])
                # 判定邏輯：ttnt 在 3 分鐘內視為在該區間運行
                if trains and 0 < int(trains[0]['ttnt']) <= 3:
                    unique_trains += 1
    return unique_trains

def is_valid(line_code, count, current_hour):
    """異常值過濾邏輯"""
    is_operational = (current_hour >= 6 or current_hour < 1)
    if is_operational and count == 0:
        return False
    # 根據你的參考資料，上限設為 40 (涵蓋 36 班巔峰用車)
    if count > 40:
        return False
    return True

# --- 主程式執行 ---
try:
    now = datetime.now()
    current_hour = now.hour
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    # 讀取現有資料
    db = {}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except: db = {}

    if date_str not in db:
        db[date_str] = {}

    # 遍歷所有目標路線進行統計
    for line in TARGET_LINES:
        count = get_line_train_count(line)
        
        # 只有數據有效才紀錄
        if is_valid(line, count, current_hour):
            # 如果是第一筆該時間的資料，建立字典
            if time_str not in db[date_str]:
                db[date_str][time_str] = {}
            # 存入格式：{"TWL": 19}
            db[date_str][time_str][line] = count

    # 儲存回 JSON
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"[{time_str}] 統計完成：{TARGET_LINES}")

except Exception as e:
    print(f"錯誤: {e}")
    exit(1)
