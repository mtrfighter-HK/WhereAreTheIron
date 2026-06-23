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

# 設定 HTML 範本目錄
templates = Jinja2Templates(directory="templates")

# ==========================================
# 💾 方案 A：Railway Volume 永久路徑設定
# ==========================================
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化資料庫
conn = get_db()
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
# 📡 背景收集器
# ==========================================
def background_collector():
    stations = [
        ("TWL", "CEN"), ("TWL", "ADM"), ("TWL", "TST"), ("TWL", "JOR"),
        ("TWL", "YMT"), ("TWL", "MOK"), ("TWL", "PRE"), ("TWL", "SSP"),
        ("TWL", "CSW"), ("TWL", "LCK"), ("TWL", "MEF"), ("TWL", "LAK"),
        ("TWL", "KWF"), ("TWL", "KWH"), ("TWL", "TWH"), ("TWL", "TSW")
    ]
    
    last_api_state = {}
    backup_day_counter = 0
    
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
                                    if ttnt_val is not None and str(ttnt_val).isdigit():
                                        ttnt_int = int(ttnt_val)
                                        dest = train.get('dest')
                                        is_delay_val = train.get('isdelay', 'N')
                                        
                                        c.execute('''INSERT INTO mtr_ttnt 
                                            (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                            (now, line, sta, direction, dest, ttnt_int, is_delay_val, now))
                                        
                                        key = f"{sta}_{direction}"
                                        if key in last_api_state:
                                            last_ttnt = last_api_state[key]
                                            if last_ttnt == 0 and ttnt_int > 0:
                                                c.execute('''INSERT INTO departure_events 
                                                    (event_time, station, direction, dest)
                                                    VALUES (?, ?, ?, ?)''',
                                                    (now, sta, direction, dest))
                                        last_api_state[key] = ttnt_int
                except Exception as e:
                    print(f"抓取車站 {sta} 失敗: {e}")
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"資料庫寫入錯誤: {e}")
            
        backup_day_counter += 1
        if backup_day_counter >= 2880:
            backup_day_counter = 0
            try:
                conn = get_db()
                conn.execute("DELETE FROM mtr_ttnt WHERE timestamp < datetime('now', '-7 days')")
                conn.execute("VACUUM")
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"定時清理失敗: {e}")

        time.sleep(30)

threading.Thread(target=background_collector, daemon=True).start()

# ==========================================
# 📬 路由 (修正 Jinja2 傳參，避免 unhashable 500 錯誤)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 🟢 修正點：顯式傳入 context= 參數，防止 FastAPI 內部雜湊報錯
    return templates.TemplateResponse(request=request, name="map.html", context={})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={})

@app.get("/api/live")
async def get_live_trains():
    conn = get_db()
    c = conn.cursor()
    # 🟢 優化點：改用更嚴謹的子查詢獲取每個站點最新的一筆紀錄，100% 避免數據重疊
    c.execute('''
        SELECT t.line, t.station, t.direction, t.dest, t.ttnt, t.is_delay 
        FROM mtr_ttnt t
        INNER JOIN (
            SELECT station, direction, MAX(timestamp) as max_ts
            FROM mtr_ttnt
            WHERE timestamp >= datetime('now', '-3 minutes') AND line = 'TWL'
            GROUP BY station, direction
        ) tm ON t.station = tm.station AND t.direction = tm.direction AND t.timestamp = tm.max_ts
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
