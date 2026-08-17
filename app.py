from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import auth, seller, buyer, products

app = FastAPI(title="E-Commerce AI", version="1.0.0")

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,     tags=["Auth"])
app.include_router(seller.router,   tags=["Seller"])
app.include_router(buyer.router,    tags=["Buyer"])
app.include_router(products.router, tags=["Products"])

# ── Serve frontend ─────────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# uvicorn app:app --reload
