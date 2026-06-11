import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import requests
import threading
import time
from datetime import datetime

app = FastAPI(title="Where Are The Iron")

templates = Jinja2Templates(directory="templates")

# ====================== 資料庫 & 收集器 (保持不變) ======================
DB_PATH = "mtr_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ... (你的資料庫初始化和 background_collector 保持不變) ...

# ====================== 路由 ======================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})   # 主頁 = 地圖

@app.get("/data", response_class=HTMLResponse)
async def data_page(request: Request):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "total": total})

# ====================== 啟動 ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)