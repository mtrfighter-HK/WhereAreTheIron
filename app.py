from flask import Flask, render_template, jsonify
import sqlite3
import requests
from datetime import datetime
import threading
import time

app = Flask(__name__, template_folder='templates')

# ====================== 資料庫 ======================
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

# ====================== 背景收集器 ======================
def background_collector():
    while True:
        try:
            test_stations = [("TWL", "CEN"), ("TWL", "TSW"), ("ISL", "CEN")]
            for line, sta in test_stations:
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
        time.sleep(60)

thread = threading.Thread(target=background_collector, daemon=True)
thread.start()

# ====================== 路由 ======================
@app.route('/')
def home():
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    return f"<h1>MTR 收集器運行中</h1><p>目前已收集 {total} 筆記錄</p><br><a href='/map'>前往地圖</a>"

@app.route('/map')
def map_page():
    return render_template('map.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)