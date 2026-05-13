from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from routers import products, counterparties, documents, transactions, stock, accounts, warehouses, units, auth
from routers import settings as settings_router

app = FastAPI(title="SkladAI API", version="1.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://rainbow-toffee-28a412.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,           prefix="/api/auth",           tags=["Auth"])
app.include_router(products.router,       prefix="/api/products",       tags=["Tovary"])
app.include_router(counterparties.router, prefix="/api/counterparties", tags=["Kontragenty"])
app.include_router(documents.router,      prefix="/api/documents",      tags=["Dokumenty"])
app.include_router(transactions.router,   prefix="/api/transactions",   tags=["Finansy"])
app.include_router(stock.router,          prefix="/api/stock",          tags=["Ostatok"])
app.include_router(accounts.router,       prefix="/api/accounts",       tags=["Scheta"])
app.include_router(warehouses.router,     prefix="/api/warehouses",     tags=["Sklady"])
app.include_router(units.router,          prefix="/api/units",          tags=["Edinicy"])
app.include_router(settings_router.router, prefix="/api/settings",      tags=["Settings"])

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