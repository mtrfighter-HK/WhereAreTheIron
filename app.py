import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import threading
import time
from datetime import datetime

app = FastAPI(title="Where Are The Iron")

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
            stations = [("TWL", "TSW"), ("TWL", "TWH"), ("TWL", "KWH"), ("TWL", "CEN"), ("TWL", "ADM")]
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

# ====================== 真實列車位置 API ======================
@app.get("/api/live")
async def get_live_trains():
    # 暫時用模擬數據，之後會從資料庫計算真實位置
    return {
        "TWL-UP-1": {"line": "TWL", "direction": "UP", "from": "CEN", "to": "TSW", "progress": 0.25, "dest": "荃灣"},
        "TWL-UP-2": {"line": "TWL", "direction": "UP", "from": "ADM", "to": "TSW", "progress": 0.65, "dest": "荃灣"},
        "TWL-DOWN-1": {"line": "TWL", "direction": "DOWN", "from": "TSW", "to": "CEN", "progress": 0.45, "dest": "中環"},
    }

# ====================== 路由 ======================
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/map.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/data", response_class=HTMLResponse)
async def data_page():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    html = f"<h1>📊 數據後台</h1><p>目前已收集 <strong>{total}</strong> 筆記錄</p><a href='/'>返回地圖</a>"
    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)