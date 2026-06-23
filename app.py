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

templates = Jinja2Templates(directory="templates")

# ==========================================
# 💾 Railway Volume 永久路徑設定
# ==========================================
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化資料庫
try:
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
except Exception as e:
    print(f"資料庫初始化失敗: {e}")

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
                                            (now, line, sta,
