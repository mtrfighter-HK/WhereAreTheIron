import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Where Are The Iron")

@app.get("/")
async def root():
    with open("templates/map.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/data")
async def data_page():
    html = """
    <h1>📊 MTR 數據後台</h1>
    <p>數據後台開發中...</p>
    <a href="/">← 返回實時地圖</a>
    """
    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)