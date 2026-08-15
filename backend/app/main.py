import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, DATA_DIR, PRODUCT_NAME, WIDGET_ALLOWED_ORIGINS
from .db import db_session, init_db
from .services import retention, retrieval
from .routers import chat, business, demo, pipeline, intelligence

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
app.include_router(demo.router)
app.include_router(pipeline.router)
app.include_router(intelligence.router)


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


DEMO_UNAVAILABLE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<title>Demo not available</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow" />
<style>
  body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f7f9; color: #222; }}
  .box {{ text-align: center; max-width: 380px; padding: 32px; }}
  h1 {{ font-size: 18px; margin: 0 0 8px; }}
  p {{ font-size: 14px; color: #666; margin: 0; }}
</style></head>
<body><div class="box"><h1>This demo link is no longer available</h1><p>{message}</p></div></body></html>"""


@app.get("/demo")
def serve_demo():
    """Public prospect-demo page for this instance (see
    docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md). Each prospect demo is its own
    isolated backend instance, so "the demo" for this instance is just its
    own generated page — no slug lookup table or shared multi-tenant state
    needed. Served directly by the instance itself (not the internal
    launcher's /file route) so it's safe to expose publicly once deployed;
    the launcher stays admin-only. Written into this instance's own
    LEADGUARD_DATA_DIR by ops/generate_site_demo.py, not the shared /widget
    directory every instance mounts.

    demo_enabled/demo_expires_at gate this the same way regardless of cause
    (never generated, expired, or disabled via Promote-to-client) — a
    visitor always sees the same clean page, never a raw 404 or a stale
    sales pitch for a business that's since become a real client."""
    demo_path = DATA_DIR / "demo.html"
    if not demo_path.exists():
        raise HTTPException(404, "No demo available for this business yet")

    with db_session() as conn:
        row = conn.execute(
            "SELECT demo_enabled, demo_expires_at FROM business WHERE id = 1"
        ).fetchone()

    if row and not row["demo_enabled"]:
        return HTMLResponse(
            DEMO_UNAVAILABLE_HTML.format(message="This link has been retired."),
            status_code=410,
            headers={"X-Robots-Tag": "noindex, nofollow"},
        )
    if row and row["demo_expires_at"]:
        try:
            expires_at = datetime.fromisoformat(row["demo_expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError:
            expires_at = None
        if expires_at and datetime.now(timezone.utc) > expires_at:
            return HTMLResponse(
                DEMO_UNAVAILABLE_HTML.format(message="This demo link has expired — reach out and we'll send a new one."),
                status_code=410,
                headers={"X-Robots-Tag": "noindex, nofollow"},
            )

    return FileResponse(
        demo_path,
        media_type="text/html",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


@app.get("/demo/video")
def serve_demo_video():
    """Optional per-prospect pitch video, dropped into this instance's own
    data dir by the Outreach video-upload flow (see ops/launcher_server.py).
    Most instances never get one — the demo template only links here when
    the video actually exists, so a 404 just means none was uploaded."""
    video_path = DATA_DIR / "demo_video.mp4"
    if not video_path.exists():
        raise HTTPException(404, "No video for this demo")
    return FileResponse(video_path, media_type="video/mp4")


app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
app.mount("/support", StaticFiles(directory=str(SUPPORT_DIR), html=True), name="support")
