from flask import Flask, render_template
import sqlite3
import requests
from datetime import datetime
import threading
import time

app = Flask(__name__, template_folder='templates')

# ====================== 資料庫設定 ======================
conn = sqlite3.connect('mtr_data.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS mtr_ttnt (
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

# ====================== 背景自動收集器 ======================
def background_collector():
    while True:
        try:
            # 先用少量站點測試，穩定後再加多
            stations = [
                ("TWL", "TSW"), ("TWL", "CEN"), ("TWL", "ADM"),
                ("ISL", "CEN"), ("ISL", "ADM")
            ]
            for line, sta in stations:
                try:
                    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line={line}&sta={sta}"
                    r = requests.get(url, timeout=10)
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
        except:
            pass
        time.sleep(60)   # 每60秒收集一次

# 啟動背景收集器
collector_thread = threading.Thread(target=background_collector, daemon=True)
collector_thread.start()

# ====================== 路由 ======================
@app.route('/')
def home():
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    return render_template('index.html', total=total)

@app.route('/map')
def map_page():
    return render_template('map.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)