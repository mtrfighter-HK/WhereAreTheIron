import os
import sqlite3
import requests
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__, template_folder='templates')

DB_PATH = '/tmp/mtr_data.db' 

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

init_db()

def background_collector():
    stations = [("TWL", "TSW"), ("TWL", "KWH"), ("TWL", "TWH"), ("TWL", "LAK"),
                ("TWL", "MEF"), ("TWL", "LCK"), ("TWL", "CSW"), ("TWL", "SSP"),
                ("TWL", "PRE"), ("TWL", "MOK"), ("TWL", "YMT"), ("TWL", "JOR"),
                ("TWL", "TST"), ("TWL", "ADM"), ("TWL", "CEN"),
                ("ISL", "CEN"), ("ISL", "ADM"), ("ISL", "WAC"), ("ISL", "CAB")]
    while True:
        try:
            local_conn = sqlite3.connect(DB_PATH)
            local_c = local_conn.cursor()
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
                                    local_c.execute('''INSERT INTO mtr_ttnt 
                                        (timestamp, line, station, direction, dest, ttnt, is_delay, collected_at)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                        (now, line, sta, direction, train.get('dest'),
                                         int(train.get('ttnt', 99)), train.get('isdelay', 'N'), now))
                except: pass
            local_conn.commit()
            local_conn.close()
        except: pass
        time.sleep(60)

threading.Thread(target=background_collector, daemon=True).start()

@app.route('/api/ttnt/<line>/<station>')
def get_ttnt(line, station):
    local_conn = sqlite3.connect(DB_PATH)
    local_c = local_conn.cursor()
    local_c.execute('SELECT direction, dest, ttnt, is_delay FROM mtr_ttnt WHERE line=? AND station=? ORDER BY timestamp DESC LIMIT 8', (line, station))
    rows = local_c.fetchall()
    local_conn.close()
    return jsonify({"station": station, "up": [r for r in rows if r[0]=='UP'][:3], "down": [r for r in rows if r[0]=='DOWN'][:3]})

@app.route('/')
def home():
    local_conn = sqlite3.connect(DB_PATH)
    local_c = local_conn.cursor()
    local_c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = local_c.fetchone()[0]
    local_conn.close()
    return render_template('index.html', total=total)

@app.route('/map')
def map_page():
    return render_template('map.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
