from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from routers import counterparties, documents, transactions, stock, accounts, warehouses, units, auth
from routers import settings as settings_router
from routers import categories, sorts, countries
from database import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="SkladAI API", version="1.0.0", redirect_slashes=False, lifespan=lifespan)

_cors_origins = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://rainbow-toffee-28a412.netlify.app,http://localhost:3000,http://localhost:5173,http://localhost:8080",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    # @app.exception_handler(Exception) is routed through ServerErrorMiddleware, which sits
    # outside CORSMiddleware.  We must add CORS headers manually so the browser can read
    # the error response instead of seeing only a CORS block.
    origin = request.headers.get("origin", "")
    extra_headers: dict = {}
    if origin in _cors_origins:
        extra_headers["Access-Control-Allow-Origin"] = origin
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=extra_headers or None,
    )


app.include_router(auth.router,           prefix="/api/auth",           tags=["Auth"])
app.include_router(counterparties.router, prefix="/api/counterparties", tags=["Kontragenty"])
app.include_router(documents.router,      prefix="/api/documents",      tags=["Dokumenty"])
app.include_router(transactions.router,   prefix="/api/transactions",   tags=["Finansy"])
app.include_router(stock.router,          prefix="/api/stock",          tags=["Ostatok"])
app.include_router(accounts.router,       prefix="/api/accounts",       tags=["Scheta"])
app.include_router(warehouses.router,     prefix="/api/warehouses",     tags=["Sklady"])
app.include_router(units.router,          prefix="/api/units",          tags=["Edinicy"])
app.include_router(settings_router.router, prefix="/api/settings",      tags=["Settings"])
app.include_router(categories.router,     prefix="/api/categories",     tags=["Kategorii"])
app.include_router(sorts.router,          prefix="/api/sorts",          tags=["Sorty"])
app.include_router(countries.router,      prefix="/api/countries",      tags=["Strany"])

_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SkladAI</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background-color: {bg_color};
      transition: background-color 0.3s ease;
    }}
    .card {{
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(8px);
      border-radius: 16px;
      padding: 40px 48px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
      text-align: center;
    }}
    h1 {{ font-size: 2rem; margin-bottom: 8px; color: #1a1a2e; }}
    p {{ color: #555; margin-bottom: 28px; }}
    .color-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      justify-content: center;
    }}
    label {{ font-size: 0.95rem; color: #333; }}
    input[type=color] {{
      width: 48px; height: 36px;
      border: none; border-radius: 8px;
      cursor: pointer; padding: 2px;
      background: none;
    }}
    button {{
      padding: 8px 20px;
      background: #4f6ef7;
      color: #fff;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: background 0.2s;
    }}
    button:hover {{ background: #3a57d6; }}
    #msg {{ margin-top: 14px; font-size: 0.85rem; color: #4f6ef7; min-height: 18px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>SkladAI API</h1>
    <p>Сервер работает — версия 1.0.0</p>
    <div class="color-row">
      <label for="picker">Цвет фона:</label>
      <input type="color" id="picker" value="{bg_color}" />
      <button onclick="saveColor()">Применить</button>
    </div>
    <div id="msg"></div>
  </div>
  <script>
    const picker = document.getElementById('picker');
    const msg    = document.getElementById('msg');

    picker.addEventListener('input', () => {{
      document.body.style.backgroundColor = picker.value;
    }});

    async function saveColor() {{
      try {{
        const res = await fetch('/api/settings/bg-color', {{
          method: 'PUT',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ color: picker.value }})
        }});
        if (res.ok) {{
          msg.textContent = 'Цвет сохранён ✓';
          setTimeout(() => msg.textContent = '', 2000);
        }} else {{
          msg.textContent = 'Ошибка при сохранении';
        }}
      }} catch(e) {{
        msg.textContent = 'Ошибка сети';
      }}
    }}
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def root():
    color = settings_router._bg_color["value"]
    return HTMLResponse(_HTML.format(bg_color=color))
