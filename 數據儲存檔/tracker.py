import requests
import json
import os
from datetime import datetime

# 設定
LINE = "TWL"
SEGMENTS = [
    ("CEN", "ADM"), ("ADM", "TST"), ("TST", "JOR"), ("JOR", "YMT"),
    ("YMT", "MOK"), ("MOK", "PRE"), ("PRE", "SSP"), ("SSP", "CSW"),
    ("CSW", "LCK"), ("LCK", "MEF"), ("MEF", "LAK"), ("LAK", "KWF"),
    ("KWF", "KWH"), ("KWH", "TWH"), ("TWH", "TSW")
]
API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
STATS_FOLDER = "數據儲存檔"
STATS_FILE = os.path.join(STATS_FOLDER, "daily_stats.json")


def get_real_count():
    unique_trains = 0
    for direction in ['UP', 'DOWN']:
        for (start, end) in SEGMENTS:
            target_sta = end if direction == 'UP' else start
            try:
                # 增加超時設定，防止 API 沒回應導致任務卡死
                res = requests.get(API_URL, params={'line': LINE, 'sta': target_sta}, timeout=15).json()
                if res.get('status') == 1:
                    data_key = f"{LINE}-{target_sta}"
                    trains = res.get('data', {}).get(data_key, {}).get(direction, [])
                    if trains and 0 < int(trains[0]['ttnt']) <= 3:
                        unique_trains += 1
            except Exception as e:
                print(f"警告: 抓取 {target_sta} 失敗: {e}")
                continue
    return unique_trains

# 執行統計
now = datetime.now()
date_str = now.strftime("%Y-%m-%d")
time_str = now.strftime("%H:%M")
current_count = get_real_count()

# 讀取現有資料 (強化防錯)
data = {}
if os.path.exists(STATS_FILE):
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
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

print(f"成功更新！偵測到 {current_count} 班車。")
