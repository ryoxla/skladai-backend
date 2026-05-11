from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import products, counterparties, documents, transactions, stock, accounts, warehouses, units, auth

app = FastAPI(title="SkladAI API", version="1.0.0", redirect_slashes=False)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router,           prefix="/api/auth",           tags=["Auth"])
app.include_router(products.router,       prefix="/api/products",       tags=["Tovary"])
app.include_router(counterparties.router, prefix="/api/counterparties", tags=["Kontragenty"])
app.include_router(documents.router,      prefix="/api/documents",      tags=["Dokumenty"])
app.include_router(transactions.router,   prefix="/api/transactions",   tags=["Finansy"])
app.include_router(stock.router,          prefix="/api/stock",          tags=["Ostatok"])
app.include_router(accounts.router,       prefix="/api/accounts",       tags=["Scheta"])
app.include_router(warehouses.router,     prefix="/api/warehouses",     tags=["Sklady"])
app.include_router(units.router,          prefix="/api/units",          tags=["Edinicy"])

@app.get("/")
def root():
    return {"status": "ok"}