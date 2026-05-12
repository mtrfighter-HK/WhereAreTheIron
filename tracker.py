import requests
import json
import os
from datetime import datetime

# 設定
LINE = "TWL"
# 定義區間清單
SEGMENTS = [
    ("CEN", "ADM"), ("ADM", "TST"), ("TST", "JOR"), ("JOR", "YMT"),
    ("YMT", "MOK"), ("MOK", "PRE"), ("PRE", "SSP"), ("SSP", "CSW"),
    ("CSW", "LCK"), ("LCK", "MEF"), ("MEF", "LAK"), ("LAK", "KWF"),
    ("KWF", "KWH"), ("KWH", "TWH"), ("TWH", "TSW")
]
API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
STATS_FILE = "daily_stats.json"

def get_real_count():
    unique_trains = 0
    # 統計全線雙向
    for direction in ['UP', 'DOWN']:
        for (start, end) in SEGMENTS:
            # 判斷目標站點：往荃灣看目標站，往中環看起點站
            target_sta = end if direction == 'UP' else start
            try:
                res = requests.get(API_URL, params={'line': LINE, 'sta': target_sta}, timeout=10).json()
                if res.get('status') == 1:
                    trains = res['data'].get(f"{LINE}-{target_sta}", {}).get(direction, [])
                    # 如果第一班車 ttnt 在 3 分鐘內，判定為在該區間行駛中
                    if trains and 0 < int(trains[0]['ttnt']) <= 3:
                        unique_trains += 1
            except:
                continue
    return unique_trains

# 獲取目前時間
now = datetime.now()
date_str = now.strftime("%Y-%m-%d")
time_str = now.strftime("%H:%M")

# 1. 獲取統計數字
current_count = get_real_count()

# 2. 讀取現有資料
if os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            data = {}
else:
    data = {}

# 3. 寫入新數據
if date_str not in data:
    data[date_str] = {}
data[date_str][time_str] = current_count

# 4. 儲存檔案
with open(STATS_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"成功於 {time_str} 統計到 {current_count} 班車。")
