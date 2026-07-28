from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, WIDGET_ALLOWED_ORIGINS
from .db import init_db
from .services import retrieval
from .routers import chat, business

PROJECT_ROOT = BASE_DIR.parent  # leadguard/
WIDGET_DIR = PROJECT_ROOT / "widget"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

app = FastAPI(title="LeadGuard")

origins = ["*"] if WIDGET_ALLOWED_ORIGINS.strip() == "*" else [o.strip() for o in WIDGET_ALLOWED_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(chat.router)
app.include_router(business.router)


@app.on_event("startup")
def on_startup():
    init_db()
    retrieval.load_index()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
