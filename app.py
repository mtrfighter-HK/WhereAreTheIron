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

# 1. 初始化 FastAPI 與 Jinja2 模板引擎
app = FastAPI(title="MTR Big Data Engine")
templates = Jinja2Templates(directory="templates")

# 📢 強制大開 CORS 綠燈，允許 CodePen 或任何前端網域前來 Fetch 數據
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== 資料庫設定 (防鎖死安全機制) ======================
def get_db_connection():
    # timeout=10 確保多線程同時讀寫時會排隊等待，避免 database is locked 錯誤
    conn = sqlite3.connect('mtr_data.db', timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # 建立改良版大數據基礎表格，包含去重唯一標籤 (train_id) 與區間進度 (progress)
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

# ====================== 背景去重數據收集器 (核心大腦) ======================
TWL_STATIONS = ["TSW", "TWH", "KWH", "KWF", "LAK", "MEF", "LCK", "CSW", "SSP", "PRE", "MOK", "YMT", "JOR", "TST", "ADM", "CEN"]
current_live_data = {} # 記憶體高效快取，供前端地圖秒讀

def get_twl_segments():
    return [(TWL_STATIONS[i], TWL_STATIONS[i+1]) for i in range(len(TWL_STATIONS) - 1)]

def background_collector():
    global current_live_data
    hk_tz = timezone(timedelta(hours=8))
    segments = get_twl_segments()
    print("🚂 [FastAPI 核心] 港鐵區間去重定位系統與歷史紀錄器已啟動...")

    while True:
        active_trains = {}
        now = datetime.now(hk_tz).isoformat()
        
        # 建立此輪掃描專屬的資料庫連線
        conn = get_db_connection()
        c = conn.cursor()

        for direction in ['UP', 'DOWN']:
            for (start_sta, end_sta) in segments:
                target_sta = end_sta if direction == 'UP' else start_sta
                from_sta = start_sta if direction == 'UP' else end_sta
                
                # 生成唯一去重列車識別碼
                train_id = f"TWL-{direction}-{from_sta}_{target_sta}"
                api_url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=TWL&sta={target_sta}"
                
                try:
                    res = requests.get(api_url, timeout=5).json()
                    if res.get('status') == 1:
                        schedule_list = res.get('data', {}).get(f'TWL-{target_sta}', {}).get(direction, [])
                        
                        for train in schedule_list:
                            ttnt = int(train.get('ttnt', 99))
                            dest = train.get('dest', '---')
                            
                            # 🎯 區間接力去重演算法 (1-3分鐘代表車在管道內)
                            if 1 <= ttnt <= 3:
                                progress = 0.85 if ttnt == 1 else (0.50 if ttnt == 2 else 0.15)
                                
                                # 1. 寫入快取記憶體 (給 /api/live 地圖用)
                                active_trains[train_id] = {
                                    "train_id": train_id, "line": "TWL", "direction": direction,
                                    "from": from_sta, "to": target_sta, "progress": progress, "dest": dest
                                }
                                
                                # 2. 寫入 SQLite 實體資料庫 (為將來分析運行圖累積歷史數據)
                                c.execute('''INSERT INTO mtr_live_history 
                                    (timestamp, train_id, line, direction, from_station, to_station, progress, dest)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                    (now, train_id, "TWL", direction, from_sta, target_sta, progress, dest))
                                break # 該區間已捕獲列車，跳出看下一個區間
                except Exception as e:
                    pass
                time.sleep(0.05) # 稍微歇息，避免請求過快被政府封鎖
                
        conn.commit()
        conn.close()
        current_live_data = active_trains
        print(f"📡 [{datetime.now(hk_tz).strftime('%H:%M:%S')}] 成功寫入資料庫，目前全綫列車：{len(active_trains)} 班")
        time.sleep(60) # 每 60 秒大掃描一次

# 啟動背景多線程爬蟲
threading.Thread(target=background_collector, daemon=True).start()


# ====================== API 接口與網頁路由 ======================

@app.get("/api/live")
def get_live_trains():
    """ 供實時地圖（map.html）經由 JavaScript Fetch 讀取最新一分鐘的去重列車進度 """
    return current_live_data

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """ 系統主頁：動態渲染 index.html 並傳入目前資料庫累積的總筆數 """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_live_history")
    total = c.fetchone()[0]
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "total": total})

@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    """ 實時地圖頁面：渲染 map.html """
    return templates.TemplateResponse("map.html", {"request": request})


# ====================== 啟動進入點 (相容本地與 Railway) ======================
if __name__ == "__main__":
    # 如果在 Railway 運行，會自動獲取環境變數 PORT；如果在本地電腦測試，預設開在 5000 埠
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
