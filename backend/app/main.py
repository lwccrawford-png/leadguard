import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, PRODUCT_NAME, WIDGET_ALLOWED_ORIGINS
from .db import init_db
from .services import retention, retrieval
from .routers import chat, business, pipeline

PROJECT_ROOT = BASE_DIR.parent  # leadguard/
WIDGET_DIR = PROJECT_ROOT / "widget"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
SUPPORT_DIR = PROJECT_ROOT / "support"

RETENTION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60

app = FastAPI(title=PRODUCT_NAME)

origins = ["*"] if WIDGET_ALLOWED_ORIGINS.strip() == "*" else [o.strip() for o in WIDGET_ALLOWED_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(chat.router)
app.include_router(business.router)
app.include_router(pipeline.router)


@app.middleware("http")
async def no_cache_dashboard(request, call_next):
    """The dashboard is actively iterated on and only ever used by us, not real
    visitors — a stale cached copy silently showing old behavior after a fix
    ships is a much worse failure mode here than the (near-zero, low-traffic
    admin tool) cost of re-fetching every time. Deliberately not applied to
    /widget — that script runs on real client sites, where caching is the
    right tradeoff for visitor page-load performance."""
    response = await call_next(request)
    if request.url.path.startswith("/dashboard"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


async def _retention_loop():
    while True:
        retention.purge_old_conversations()
        await asyncio.sleep(RETENTION_CHECK_INTERVAL_SECONDS)


@app.on_event("startup")
async def on_startup():
    init_db()
    retrieval.load_index()
    retention.purge_old_conversations()
    asyncio.create_task(_retention_loop())


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
app.mount("/support", StaticFiles(directory=str(SUPPORT_DIR), html=True), name="support")
