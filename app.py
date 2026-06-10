import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
import time
import threading
from datetime import datetime, timedelta, timezone
import uvicorn

# 初始化 FastAPI 與 Jinja2 模板引擎
app = FastAPI(title="MTR Big Data Engine")
templates = Jinja2Templates(directory="templates")

# 強制大開 CORS 綠燈
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== 資料庫設定 ======================
# 確保伺服器上有這個資料夾，避免 SQLite 找不到路徑報錯
if not os.path.exists('數據儲存檔'):
    os.makedirs('數據儲存檔')

def get_db_connection():
    # 連線到資料夾內的 db 檔案
    conn = sqlite3.connect('數據儲存檔/mtr_data.db', timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

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

# 執行資料庫初始化
init_db()

# ====================== 背景去重數據收集器 ======================
TWL_STATIONS = ["TSW", "TWH", "KWH", "KWF", "LAK", "MEF", "LCK", "CSW", "SSP", "PRE", "MOK", "YMT", "JOR", "TST", "ADM", "CEN"]
current_live_data = {} 

def get_twl_segments():
    return [(TWL_STATIONS[i], TWL_STATIONS[i+1]) for i in range(len(TWL_STATIONS) - 1)]

def background_collector():
    global current_live_data
    hk_tz = timezone(timedelta(hours=8))
    segments = get_twl_segments()
    print("🚂 [FastAPI 核心] 港鐵區間去重定位系統已啟動...")

    while True:
        active_trains = {}
        now = datetime.now(hk_tz).isoformat()
        
        conn = get_db_connection()
        c = conn.cursor()

        for direction in ['UP', 'DOWN']:
            for (start_sta, end_sta) in segments:
                target_sta = end_sta if direction == 'UP' else start_sta
                from_sta = start_sta if direction == 'UP' else end_sta
                
                train_id = f"TWL-{direction}-{from_sta}_{target_sta}"
                api_url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=TWL&sta={target_sta}"
                
                try:
                    res = requests.get(api_url, timeout=5).json()
                    if res.get('status') == 1:
                        schedule_list = res.get('data', {}).get(f'TWL-{target_sta}', {}).get(direction, [])
                        
                        for train in schedule_list:
                            ttnt = int(train.get('ttnt', 99))
                            dest = train.get('dest', '---')
                            
                            if 1 <= ttnt <= 3:
                                progress = 0.85 if ttnt == 1 else (0.50 if ttnt == 2 else 0.15)
                                
                                active_trains[train_id] = {
                                    "train_id": train_id, "line": "TWL", "direction": direction,
                                    "from": from_sta, "to": target_sta, "progress": progress, "dest": dest
                                }
                                
                                c.execute('''INSERT INTO mtr_live_history 
                                    (timestamp, train_id, line, direction, from_station, to_station, progress, dest)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                    (now, train_id, "TWL", direction, from_sta, target_sta, progress, dest))
                                break 
                except Exception:
                    pass
                time.sleep(0.05) 
                
        conn.commit()
        conn.close()
        current_live_data = active_trains
        print(f"📡 成功寫入資料庫，目前全綫列車：{len(active_trains)} 班")
        time.sleep(60) 

# 啟動背景多線程爬蟲
threading.Thread(target=background_collector, daemon=True).start()

# ====================== API 接口與網頁路由 ======================

@app.get("/api/live")
def get_live_trains():
    return current_live_data

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_live_history")
    total = c.fetchone()[0]
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "total": total})

@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

# ====================== 啟動進入點 ======================
if __name__ == "__main__":
    # 這裡會優先使用 Railway 自動分配的 PORT，若無則預設為 8080
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
