import os
import sqlite3
import requests
import threading
import time
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

app = FastAPI(title="MTR 實時地圖")

# ====================== 資料庫 ======================
DB_PATH = "mtr_data.db"

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
conn.commit()
conn.close()

# ====================== 背景收集器 ======================
def background_collector():
    while True:
        try:
            stations = [("TWL", "TSW"), ("TWL", "CEN"), ("ISL", "CEN")]
            conn = get_db()
            c = conn.cursor()
            for line, sta in stations:
                try:
                    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line={line}&sta={sta}"
                    r = requests.get(url, timeout=8)
                    if r.status_code == 200:
                        data = r.json().get('data', {}).get(f'{line}-{sta}', {})
                        now = datetime.now().isoformat()
                        for direction in ['UP', 'DOWN']:
                            if direction in data:
                                for train in data[direction]:
                                    c.execute('''INSERT INTO mtr_ttnt 
                                        (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                        (now, line, sta, direction, train.get('dest'),
                                         int(train.get('ttnt', 99)), train.get('isdelay', 'N'), now))
                except:
                    pass
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(60)

threading.Thread(target=background_collector, daemon=True).start()

# ====================== 路由變更 ======================

@app.get("/", response_class=HTMLResponse)
async def home():
    # 點入網站首頁，直接顯示實時地圖
    template_path = os.path.join("templates", "map.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>地圖檔案 templates/map.html 不存在</h1>", status_code=404)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    # 原本的首頁變成了數據管理後台
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>MTR 收集器數據後台</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #fafafa; }}
            .card {{ background: white; padding: 30px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #E2231A; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; }}
            .btn:hover {{ background: #b61c14; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚇 MTR 數據收集後台</h1>
            <p style="font-size: 18px;">系統目前已在 SQLite 資料庫安全建立 <strong>{total}</strong> 筆列車進站紀錄。</p>
            <a href="/" class="btn">🗺️ 返回實時地圖首頁</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

# ====================== 實時列車位置 API ======================
@app.get("/api/live")
async def get_live_trains():
    conn = get_db()
    c = conn.cursor()
    # 撈出最近 5 分鐘內每個車站最新的一筆紀錄，確保數據連續性
    c.execute('''
        SELECT line, station, direction, dest, ttnt, is_delay, timestamp 
        FROM mtr_ttnt 
        WHERE timestamp >= datetime('now', '-5 minutes')
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

# ====================== 替代 StaticFiles 方案：安全安全讀取 GeoJSON ======================
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

# ====================== 啟動 ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
