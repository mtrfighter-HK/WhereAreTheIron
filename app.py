import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Where Are The Iron")

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def root(request: Request):
    try:
        return templates.TemplateResponse("map.html", {"request": request})
    except Exception as e:
        return HTMLResponse(f"<h1>模板載入錯誤: {str(e)}</h1>")

@app.get("/data")
async def data_page(request: Request):
    return HTMLResponse("<h1>數據後台 (開發中)</h1><a href='/'>返回地圖</a>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)