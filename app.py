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

# ====================== 荃灣線站序 ======================
TWL_STATIONS = ["CEN", "ADM", "TST", "JOR", "YMT", "MOK", "PRE", "SSP", "CSW", "LCK", "MEF", "LAK", "KWF", "KWH", "TWH", "TSW"]

# ====================== 背景收集器 ======================
def background_collector():
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            for sta in TWL_STATIONS:
                try:
                    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=TWL&sta={sta}"
                    r = requests.get(url, timeout=8)
                    if r.status_code == 200:
                        data = r.json().get('data', {}).get(f'TWL-{sta}', {})
                        now = datetime.now().isoformat()
                        for direction in ['UP', 'DOWN']:
                            if direction in data:
                                for train in data[direction]:
                                    c.execute('''INSERT INTO mtr_ttnt 
                                        (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                        (now, "TWL", sta, direction, train.get('dest'),
                                         int(train.get('ttnt', 99)), train.get('isdelay', 'N'), now))
                except:
                    pass
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(60)

threading.Thread(target=background_collector, daemon=True).start()

# ====================== Live API ======================
@app.get("/api/live")
async def get_live_trains():
    # 暫時返回模擬數據（之後會改成從資料庫計算真實位置）
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
    try:
        live_data = get_live_trains()
    except:
        live_data = {"error": "無法獲取"}
    
    html = f"""
    <html>
    <head><meta charset="UTF-8"><title>MTR 數據後台</title></head>
    <body style="font-family:Arial; padding:20px; line-height:1.6;">
        <h1>📊 MTR 數據後台</h1>
        <p><a href="/">← 返回地圖</a></p>
        <h2>/api/live 返回數據：</h2>
        <pre style="background:#f4f4f4; padding:15px; border-radius:8px; overflow:auto; font-size:14px; white-space:pre-wrap;">{live_data}</pre>
    </body>
    </html>
    """
    return HTMLResponse(html)

# ====================== 實時列車位置 API ======================
@app.get("/api/live")
async def get_live_trains():
    conn = get_db()
    c = conn.cursor()
    
    # 撈出最近 2 分鐘內每個車站、每個方向最新的一筆列車紀錄
    # 這樣可以確保拿到的數據是最即時、沒有斷訊的
    c.execute('''
        SELECT line, station, direction, dest, ttnt, is_delay, timestamp 
        FROM mtr_ttnt 
        WHERE timestamp >= datetime('now', '-2 minutes')
        GROUP BY line, station, direction
        ORDER BY timestamp DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    # 整理成乾淨的 JSON 格式傳給前端地圖
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

# ====================== 啟動 ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)