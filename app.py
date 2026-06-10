import os
import sqlite3
import requests
from flask import Flask, render_template, jsonify

app = Flask(__name__, template_folder='templates')
DB_PATH = '/tmp/mtr_data.db'

@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS mtr_ttnt (id INTEGER PRIMARY KEY, timestamp TEXT)")
    c.execute("SELECT COUNT(*) FROM mtr_ttnt")
    total = c.fetchone()[0]
    conn.close()
    return render_template('index.html', total=total)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
