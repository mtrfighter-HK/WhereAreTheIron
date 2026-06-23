import os
import sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

# 允許跨域請求（避免前端 Leaflet 呼叫時被封鎖）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 設定 HTML 範本目錄
templates = Jinja2Templates(directory="templates")

# ==========================================
# 💾 Railway Volume 永久路徑與多執行緒安全設定
# ==========================================
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_live.db")

def get_db_connection():
    # 加上 check_same_thread=False 防止 APScheduler 與 FastAPI 路由衝突引發 500 錯誤
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 原始數據表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS train_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            station TEXT,
            direction TEXT,
            ttnt INTEGER,
            dest TEXT
        )
    ''')
    # 聚合後的班次發車時間表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departure_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            station TEXT,
            direction TEXT,
            dest TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 📡 數據收集器 (Collector) & 發車事件捕捉
# ==========================================
last_api_state = {}

def fetch_mtr_data():
    global last_api_state
    try:
        train_data = get_current_mtr_schedule()
        
        if train_data and isinstance(train_data, list):
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for train in train_data:
                if train.get("line") != "TWL": continue
                sta = str(train.get("station", "")).upper()
                dir_ = train.get("direction", "")
                ttnt = int(train.get("ttnt", 0))
                dest = train.get("dest", "")
                
                # 1. 寫入原始紀錄
                cursor.execute(
                    "INSERT INTO train_records (station, direction, ttnt, dest) VALUES (?, ?, ?, ?)",
                    (sta, dir_, ttnt, dest)
                )
                
                # 2. 核心發車事件捕捉 (0 變大)
                key = f"{sta}_{dir_}"
                if key in last_api_state:
                    last_ttnt = last_api_state[key]
                    if last_ttnt == 0 and ttnt > 0:
                        cursor.execute(
                            "INSERT INTO departure_events (station, direction, dest) VALUES (?, ?, ?)",
                            (sta, dir_, dest)
                        )
                last_api_state[key] = ttnt
                
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"後台收集器背景運作中... 訊息: {e}")

# 核心功能函數：請在此處原封不動黏貼你原本抓取港鐵 API 的核心 Requests 邏輯！
def get_current_mtr_schedule():
    try:
        # 🟢 請在此處保持或貼回你之前能向港鐵成功拿到資料的 URL 與 filtration 邏輯
        return [] 
    except Exception as e:
        print(f"抓取港鐵數據失敗: {e}")
        return []

# 每 12 秒後台自動運行收集
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_mtr_data, 'interval', seconds=12)
scheduler.start()

# ==========================================
# 📬 FastAPI 路由
# ==========================================

@app.get('/api/live')
async def api_live():
    try:
        data = get_current_mtr_schedule()
        return {"status": "success", "data": data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get('/api/admin/departures')
async def api_admin_departures(station: str = ""):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if station and station != 'ALL':
            cursor.execute(
                "SELECT event_time, station, direction, dest FROM departure_events WHERE station = ? ORDER BY event_time DESC LIMIT 50",
                (station.upper(),)
            )
        else:
            cursor.execute("SELECT event_time, station, direction, dest FROM departure_events ORDER BY event_time DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()
        return {"status": "success", "data": [dict(row) for row in rows]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get('/api/admin/stats')
async def api_admin_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM train_records")
        total_records = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM departure_events")
        total_events = cursor.fetchone()[0]
        conn.close()
        return {"total_records": total_records, "total_departures": total_events}
    except Exception as e:
        return {"total_records": 0, "total_departures": 0}

@app.get('/', response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

@app.get('/admin', response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# ==========================================
# 🚀 啟動區塊 (Railway 部署最核心部分)
# ==========================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
