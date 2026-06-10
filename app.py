import os
import sqlite3
import requests
import time
import threading
import uvicorn
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# 初始化
app = FastAPI(title="MTR Big Data Engine")
templates = Jinja2Templates(directory="templates")

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 資料庫連線函數 (不使用子目錄，直接存入根目錄避免路徑權限問題)
def get_db_connection():
    # 將這行改為：
conn = sqlite3.connect('/tmp/mtr_data.db', timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化資料庫
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mtr_live_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        train_id TEXT,
        line TEXT,
        direction TEXT,
        from_station TEXT,
        to_station TEXT,
        progress REAL,
        dest TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# 全域變數
current_live_data = {}
TWL_STATIONS = ["TSW", "TWH", "KWH", "KWF", "LAK", "MEF", "LCK", "CSW", "SSP", "PRE", "MOK", "YMT", "JOR", "TST", "ADM", "CEN"]

def background_collector():
    global current_live_data
    hk_tz = timezone(timedelta(hours=8))
    while True:
        try:
            active_trains = {}
            conn = get_db_connection()
            c = conn.cursor()
            
            # 簡化掃描邏輯
            for direction in ['UP', 'DOWN']:
                for i in range(len(TWL_STATIONS) - 1):
                    start_sta = TWL_STATIONS[i]
                    end_sta = TWL_STATIONS[i+1]
                    target_sta = end_sta if direction == 'UP' else start_sta
                    from_sta = start_sta if direction == 'UP' else end_sta
                    
                    train_id = f"TWL-{direction}-{from_sta}_{target_sta}"
                    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=TWL&sta={target_sta}"
                    
                    res = requests.get(url, timeout=5).json()
                    if res.get('status') == 1:
                        data = res.get('data', {}).get(f'TWL-{target_sta}', {}).get(direction, [])
                        for train in data:
                            ttnt = int(train.get('ttnt', 99))
                            if 1 <= ttnt <= 3:
                                progress = 0.85 if ttnt == 1 else (0.50 if ttnt == 2 else 0.15)
                                active_trains[train_id] = {
                                    "train_id": train_id, "direction": direction,
                                    "from": from_sta, "to": target_sta, "progress": progress, "dest": train.get('dest')
                                }
                                c.execute("INSERT INTO mtr_live_history (timestamp, train_id, line, direction, from_station, to_station, progress, dest) VALUES (?,?,?,?,?,?,?,?)",
                                          (datetime.now(hk_tz).isoformat(), train_id, "TWL", direction, from_sta, target_sta, progress, train.get('dest')))
            conn.commit()
            conn.close()
            current_live_data = active_trains
        except Exception as e:
            print(f"Collector Error: {e}")
        time.sleep(60)

threading.Thread(target=background_collector, daemon=True).start()

# 路由
@app.get("/api/live")
def get_live():
    return current_live_data

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_live_history")
    total = c.fetchone()[0]
    conn.close()
    # 確保傳遞參數格式乾淨
    return templates.TemplateResponse("index.html", {"request": request, "total": total})

@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

# 啟動設定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
