import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Where Are The Iron")

@app.get("/")
async def root():
    return HTMLResponse("""
        <h1>✅ 測試成功！</h1>
        <p>app.py 已經可以正常運行</p>
        <a href="/map">前往地圖</a>
    """)

@app.get("/map")
async def map_page():
    return HTMLResponse("<h1>🗺️ 地圖頁面（即將加入完整功能）</h1>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)