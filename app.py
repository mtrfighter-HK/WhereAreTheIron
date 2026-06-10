import os
from fastapi import FastAPI, Request
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

conn = get_db()
conn.execute('''CREATE TABLE IF NOT EXISTS mtr_ttnt (...)''')  # 保持你現有資料庫初始化
conn.commit()
conn.close()

# 背景收集器（保持你現有版本）
def background_collector():
    # ... 你現有的 background_collector 代碼 ...
    pass

threading.Thread(target=background_collector, daemon=True).start()

# ====================== 新增 Live API ======================
current_live_data = {}

@app.get("/api/live")
async def get_live_trains():
    return current_live_data

# 主頁和地圖頁面
@app.get("/", response_class=HTMLResponse)
async def home():
    # ... 你現有的主頁代碼 ...
    pass

@app.get("/map", response_class=HTMLResponse)
async def map_page():
    with open("templates/map.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)