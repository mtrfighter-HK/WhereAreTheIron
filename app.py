from flask import Flask, render_template, jsonify
import sqlite3
import requests
from datetime import datetime
import threading
import time

app = Flask(__name__, template_folder='templates')

# 資料庫位置：使用 Railway 的臨時目錄 /tmp
DB_PATH = '/tmp/mtr_data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

# 背景自動收集器
def background_collector():
    while True:
        try:
            # 簡化版站點清單，避免清單過長導致請求超時
            stations = [("TWL", "TSW"), ("TWL", "CEN"), ("ISL", "CEN"), ("ISL", "CAB")]
            for line, sta in stations:
                url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line={line}&sta={sta}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json().get('data', {}).get(f'{line}-{sta}', {})
                    now = datetime.now().isoformat()
                    for direction in ['UP', 'DOWN']:
                        if direction in data:
                            for train in data[direction]:
                                c.execute('INSERT INTO mtr_ttnt (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                          (now, line, sta, direction, train.get('dest'), int(train.get('ttnt', 99)), train.get('isdelay', 'N'), now))
            conn.commit()
        except:
            pass
        time.sleep(60)

threading.Thread(target=background_collector, daemon=True).start()

# 路由
@app.route('/')
def home():
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    return render_template('index.html', total=total)

@app.route('/map')
def map_page():
    return render_template('map.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
