import os
import sqlite3
import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
CORS(app)

# ==========================================
# 💾 方案 A：Railway Volume 永久路徑設定
# ==========================================
# 如果在 Railway 環境，使用 /app/data 永久目錄，本機測試則用當前目錄
DB_DIR = "/app/data" if os.path.exists("/app/data") else "."
DB_PATH = os.path.join(DB_DIR, "mtr_live.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 原始數據表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS train_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            station TEXT,
            direction TEXT,
            ttnt INTEGER,
            dest TEXT
        )
    ''')
    # 聚合後的班次發車時間表（供歷史查詢與未來大數據分析）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departure_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            station TEXT,
            direction TEXT,
            dest TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 📡 數據收集器 (Collector) & 發車事件捕捉
# ==========================================
# 記錄上一次各站的 ttnt 狀態，用來偵測「0 變大」的發車瞬間
last_api_state = {}

def fetch_mtr_data():
    global last_api_state
    try:
        # 這裡換成你實際抓取港鐵 API 的 URL（以下為模擬或你的實時代理路徑）
        # 假設你的 API 來源是港鐵官方或補全後的數據
        url = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=TWL&sta=CEN" # 範例，請依你實際運作調整
        # 如果你有自己寫好的多站循環抓取，請保留原本的抓取邏輯。
        # 這裡示範將抓到的 TWL 數據寫入 DB
        
        # 模擬呼叫你的 live api 獲取全線數據
        response = requests.get("http://127.0.0.1:5000/api/live" if DB_DIR=="." else "https://"+request.host+"/api/live")
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                train_data = res_json.get("data", [])
                
                conn = get_db_connection()
                cursor = conn.cursor()
                
                for train in train_data:
                    if train.get("line") != "TWL": continue
                    sta = train["station"].toUpperCase()
                    dir_ = train["direction"]
                    ttnt = int(train["ttnt"])
                    dest = train["dest"]
                    
                    # 1. 寫入原始紀錄
                    cursor.execute(
                        "INSERT INTO train_records (station, direction, ttnt, dest) VALUES (?, ?, ?, ?)",
                        (sta, dir_, ttnt, dest)
                    )
                    
                    # 2. 核心發車事件捕捉 (0 變大)
                    key = f"{sta}_{dir_}"
                    if key in last_api_state:
                        last_ttnt = last_api_state[key]
                        if last_ttnt == 0 and ttnt > 0:
                            # 捕捉到發車！寫入事件表
                            cursor.execute(
                                "INSERT INTO departure_events (station, direction, dest) VALUES (?, ?, ?)",
                                (sta, dir_, dest)
                            )
                    last_api_state[key] = ttnt
                    
                conn.commit()
                conn.close()
    except Exception as e:
        print(f"後台收集器出錯: {e}")

# 每 12 秒後台自動運行收集
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_mtr_data, 'interval', seconds=12)
scheduler.start()

# ==========================================
# 📬 API 路由
# ==========================================

# 模擬/實際的實時 API 接口（供地圖與後台看板使用）
@app.route('/api/live')
def api_live():
    # 這裡放你原本從港鐵 API 撈取並過濾的邏輯
    # 確保回傳格式為 {"status": "success", "data": [...]}
    try:
        # 暫代：讀取你目前的真實即時數據來源
        # 請在此處保留或黏貼你原本的港鐵 API 請求與 json 解析代碼
        return jsonify({"status": "success", "data": []}) 
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# 後台數據篩選 API：獲取特定車站與時段的開出班次
@app.route('/api/admin/departures')
def api_admin_departures():
    station = request.args.get('station', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if station and station != 'ALL':
        cursor.execute(
            "SELECT event_time, station, direction, dest FROM departure_events WHERE station = ? ORDER BY event_time DESC LIMIT 50",
            (station.toUpperCase(),)
        )
    else:
        cursor.execute("SELECT event_time, station, direction, dest FROM departure_events ORDER BY event_time DESC LIMIT 50")
        
    rows = cursor.fetchall()
    conn.close()
    
    events = [dict(row) for row in rows]
    return jsonify({"status": "success", "data": events})

# 後台統計 API：獲取總收集量
@app.route('/api/admin/stats')
def api_admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM train_records")
    total_records = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM departure_events")
    total_events = cursor.fetchone()[0]
    conn.close()
    return jsonify({"total_records": total_records, "total_departures": total_events})

# 頁面跳轉
@app.route('/')
def index_page():
    return render_template('map.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
