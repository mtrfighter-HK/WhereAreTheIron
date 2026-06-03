from flask import Flask, render_template
import sqlite3
import requests
from datetime import datetime
import threading
import time

app = Flask(__name__, template_folder='templates')

# 資料庫
conn = sqlite3.connect('mtr_data.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS mtr_ttnt (...)''')  # 保持你原有表格
conn.commit()

# 背景收集器（保持運行）
def background_collector():
    while True:
        # ... 你原有收集程式 ...
        time.sleep(60)

thread = threading.Thread(target=background_collector, daemon=True)
thread.start()

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