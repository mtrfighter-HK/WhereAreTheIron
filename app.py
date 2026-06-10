import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
import threading
import time                     # ← 這一行是關鍵，之前漏了
from datetime import datetime

app = FastAPI(title="MTR 實時地圖")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== 資料庫 ======================
DB_PATH = "mtr_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
            stations = [
                ("TWL", "TSW"), ("TWL", "TWH"), ("TWL", "KWH"), ("TWL", "CEN"),
                ("TWL", "ADM"), ("ISL", "CEN"), ("ISL", "ADM")
            ]
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

# 啟動收集器
threading.Thread(target=background_collector, daemon=True).start()

# ====================== 路由 ======================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "total": total})

@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

@app.get("/api/ttnt/{line}/{station}")
async def get_ttnt(line: str, station: str):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT direction, dest, ttnt, is_delay 
                 FROM mtr_ttnt 
                 WHERE line=? AND station=? 
                 ORDER BY timestamp DESC LIMIT 6''', (line, station))
    rows = c.fetchall()
    conn.close()
    return {"up": [dict(row) for row in rows if row["direction"] == "UP"],
            "down": [dict(row) for row in rows if row["direction"] == "DOWN"]}

# ====================== 啟動 ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)