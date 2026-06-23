import os
import sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

# 設定 HTML 範本目錄
templates = Jinja2Templates(directory="templates")

# ==========================================
# 💾 方案 A：Railway Volume 永久路徑設定
# ==========================================
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_live.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
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
        # 注意：請將此處的 URL 替換為你原本後台實際向港鐵或外部抓取數據的 Python 邏輯
        # 這裡示範基本的數據寫入與發車監聽
        # 假設從你原本能正常運作的數據源獲取到 train_data
        train_data = [] 
        
        if train_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for train in train_data:
                if train.get("line") != "TWL": continue
                sta = train["station"].upper()
                dir_ = train["direction"]
                ttnt = int(train["ttnt"])
                dest = train["dest"]
                
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
        print(f"後台收集器出錯: {e}")

# 每 12 秒後台自動運行收集
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_mtr_data, 'interval', seconds=12)
scheduler.start()

# ==========================================
# 📬 FastAPI 路由 (完美替代原本的 Flask 路由)
# ==========================================

# 1. 實時 API 接口（供地圖與後台看板使用）
@app.get('/api/live')
async def api_live():
    # 💡 重要：請在此處原封不動地「黏貼」你原本 app.py 內抓取、過濾港鐵 API 的核心程式碼！
    # 確保最後回傳格式為 JSON: {"status": "success", "data": [...]}
    try:
        # 暫代虛擬數據結構，請覆蓋為你的真實港鐵抓取邏輯
        return {"status": "success", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 2. 後台數據篩選 API
@app.get('/api/admin/departures')
async def api_admin_departures(station: str = ""):
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

# 3. 後台統計 API
@app.get('/api/admin/stats')
async def api_admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM train_records")
    total_records = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM departure_events")
    total_events = cursor.fetchone()[0]
    conn.close()
    return {"total_records": total_records, "total_departures": total_events}

# 4. 頁面渲染路由 (使用 FastAPI Jinja2)
@app.get('/', response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

@app.get('/admin', response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})
