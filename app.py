import os
import sqlite3
import requests
import threading
import time
import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="MTR 實時地圖 - 荃灣綫 大數據持久化版")

# 設定 HTML 範本目錄 (FastAPI 用)
templates = Jinja2Templates(directory="templates")

# ==========================================
# 💾 方案 A：Railway Volume 永久路徑設定
# ==========================================
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_data.db")

def get_db():
    # 加上 check_same_thread=False 確保多執行緒背景寫入與 FastAPI 讀取不會引發 500 錯誤
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化資料庫
conn = get_db()
# 1. 原始紀錄表
conn.execute('''CREATE TABLE IF NOT EXISTS mtr_ttnt (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    line TEXT,
    station TEXT,
    direction TEXT,
    dest TEXT,
    ttnt INTEGER,
    is_delay TEXT,
    collected_at TEXT
)''')
# 2. 聚合後的實際發車班次表 (0 變大)
conn.execute('''CREATE TABLE IF NOT EXISTS departure_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT,
    station TEXT,
    direction TEXT,
    dest TEXT
)''')
conn.commit()
conn.close()

# ==========================================
# 📡 背景收集器（結合發車事件捕捉與自動清理機制）
# ==========================================
def background_collector():
    stations = [
        ("TWL", "CEN"), ("TWL", "ADM"), ("TWL", "TST"), ("TWL", "JOR"),
        ("TWL", "YMT"), ("TWL", "MOK"), ("TWL", "PRE"), ("TWL", "SSP"),
        ("TWL", "CSW"), ("TWL", "LCK"), ("TWL", "MEF"), ("TWL", "LAK"),
        ("TWL", "KWF"), ("TWL", "KWH"), ("TWL", "TWH"), ("TWL", "TSW")
    ]
    
    last_api_state = {} # 記憶體追蹤各站上一秒的 ttnt 狀態
    backup_day_counter = 0 # 用來計算天數進行 GitHub 備份
    
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now = datetime.now().isoformat()
            
            for line, sta in stations:
                try:
                    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line={line}&sta={sta}"
                    r = requests.get(url, timeout=8)
                    if r.status_code == 200:
                        data = r.json().get('data', {}).get(f'{line}-{sta}', {})
                        for direction in ['UP', 'DOWN']:
                            if direction in data:
                                for train in data[direction]:
                                    ttnt_val = train.get('ttnt')
                                    # 港鐵 API ttnt=0 或者是大於0的數字都是有效數據
                                    if ttnt_val is not None and str(ttnt_val).isdigit():
                                        ttnt_int = int(ttnt_val)
                                        dest = train.get('dest')
                                        is_delay_val = train.get('isdelay', 'N')
                                        
                                        # 1. 寫入原始紀錄
                                        c.execute('''INSERT INTO mtr_ttnt 
                                            (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                            (now, line, sta, direction, dest, ttnt_int, is_delay_val, now))
                                        
                                        # 2. 核心發車捕捉邏輯 (當前是正整數，且上次記憶是0)
                                        key = f"{sta}_{direction}"
                                        if key in last_api_state:
                                            last_ttnt = last_api_state[key]
                                            if last_ttnt == 0 and ttnt_int > 0:
                                                c.execute('''INSERT INTO departure_events 
                                                    (event_time, station, direction, dest)
                                                    VALUES (?, ?, ?, ?)''',
                                                    (now, sta, direction, dest))
                                                print(f"🚀 [後台捕捉發車] {sta} 往 {dest} ({direction})")
                                                
                                        last_api_state[key] = ttnt_int
                except Exception as e:
                    print(f"抓取車站 {sta} 失敗: {e}")
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"資料庫寫入錯誤: {e}")
            
        # ==========================================
        # 📦 預留：定時匯出 JSON 並清理 SQLite 空間
        # ==========================================
        backup_day_counter += 1
        if backup_day_counter >= 2880: # 大約每 24 小時執行一次清理檢查 (30秒 * 2880 = 24小時)
            backup_day_counter = 0
            try:
                # 這裡未來可以接入 GitHub API 將舊數據推送到 Repository
                print("📅 [自動化排程] 開始執行 SQLite 資料瘦身與 GitHub 冷數據備份檢查...")
                # 刪除 7 天前的原始爆量數據，保持 Volume 輕量
                conn = get_db()
                conn.execute("DELETE FROM mtr_ttnt WHERE timestamp < datetime('now', '-7 days')")
                conn.execute("VACUUM")
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"定時清理失敗: {e}")

        # 每 30 秒抓取一次（保持你原本完美的即時性設定）
        time.sleep(30)

threading.Thread(target=background_collector, daemon=True).start()

# ==========================================
# 📬 路由 (完美相容原本的 GeoJSON 讀取)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 使用 FastAPI Jinja2 渲染，確保穩定性
    return templates.TemplateResponse("map.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    # 跳轉渲染你剛才看到的全新升級版數據後台
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/live")
async def get_live_trains():
    conn = get_db()
    c = conn.cursor()
    # 保持你原本完美的「撈出最近 3 分鐘最新紀錄」
    c.execute('''
        SELECT line, station, direction, dest, ttnt, is_delay, timestamp 
        FROM mtr_ttnt 
        WHERE timestamp >= datetime('now', '-3 minutes') AND line = 'TWL'
        GROUP BY line, station, direction
        ORDER BY timestamp DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    trains = []
    for row in rows:
        trains.append({
            "line": row["line"],
            "station": row["station"],
            "direction": row["direction"],
            "dest": row["dest"],
            "ttnt": row["ttnt"],
            "is_delay": row["is_delay"]
        })
    return {"status": "success", "data": trains}

# 後台專用 API 1：獲取特定車站與時段的開出班次歷史紀錄
@app.get('/api/admin/departures')
async def api_admin_departures(station: str = ""):
    conn = get_db()
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

# 後台專用 API 2：獲取持久化儲存總量統計
@app.get('/api/admin/stats')
async def api_admin_stats():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mtr_ttnt")
        total_records = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM departure_events")
        total_events = cursor.fetchone()[0]
        conn.close()
        return {"total_records": total_records, "total_departures": total_events}
    except Exception:
        return {"total_records": 0, "total_departures": 0}

# ====================== 讀取 GeoJSON 路由 ======================
@app.get("/系統基本檔/StationLocation_2026_06.geojson")
async def get_station_geojson():
    file_path = os.path.join("系統基本檔", "StationLocation_2026_06.geojson")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/路線軌道檔/Track.TsuenWanLine.geojson")
async def get_track_geojson():
    file_path = os.path.join("路線軌道檔", "Track.TsuenWanLine.geojson")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"error": "File not found"}, status_code=404)

# ==========================================
# 🚀 啟動區塊 (完美保留環境變數 PORT 監聽)
# ==========================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
