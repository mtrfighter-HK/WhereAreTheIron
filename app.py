from flask import Flask, render_template, jsonify
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
            # 擴大收集範圍
            stations = [
                ("TWL", "TSW"), ("TWL", "KWH"), ("TWL", "KWF"), ("TWL", "LAK"),
                ("TWL", "MEF"), ("TWL", "LCK"), ("TWL", "CSW"), ("TWL", "SSP"),
                ("TWL", "PRE"), ("TWL", "MOK"), ("TWL", "YMT"), ("TWL", "JOR"),
                ("TWL", "TSI"), ("TWL", "ADM"), ("TWL", "CEN"),
                ("ISL", "CEN"), ("ISL", "ADM"), ("ISL", "WAC"), ("ISL", "CAB")
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 收集完成")
        except:
            pass
        time.sleep(60)

# 啟動背景收集器
background_thread = threading.Thread(target=background_collector, daemon=True)
background_thread.start()

# ====================== 新增 API ======================
@app.route('/api/ttnt/<line>/<station>')
def get_ttnt(line, station):
    c.execute('''SELECT direction, dest, ttnt, is_delay 
                 FROM mtr_ttnt 
                 WHERE line=? AND station=? 
                 ORDER BY timestamp DESC LIMIT 8''', (line, station))
    rows = c.fetchall()
    
    up = [row for row in rows if row[0] == 'UP']
    down = [row for row in rows if row[0] == 'DOWN']
    
    return jsonify({
        "station": station,
        "up": up[:3],
        "down": down[:3]
    })

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