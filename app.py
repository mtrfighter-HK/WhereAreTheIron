import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import threading
import time
from datetime import datetime

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

# ====================== 路由 ======================
@app.get("/", response_class=HTMLResponse)
async def home():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>MTR 收集器</title></head>
    <body style="font-family:Arial;text-align:center;padding:50px;">
        <h1>🚇 MTR 收集器運行中</h1>
        <p>目前已收集 <strong>{total}</strong> 筆記錄</p>
        <a href="/map" style="font-size:20px;color:blue;">🗺️ 前往實時地圖</a>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/map", response_class=HTMLResponse)
async def map_page():
    return HTMLResponse("<h1>地圖頁面建設中...</h1><p>稍後會加入 Leaflet 地圖</p>")

# ====================== 啟動 ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)