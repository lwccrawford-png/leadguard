"""Prospect demo engagement tracking (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md, Phase 2).

Each prospect demo is its own isolated instance (see CLAUDE.md), so events recorded here
always belong to exactly this instance's one demo — no prospect_demo_id / slug lookup needed.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import DATA_DIR
from ..db import db_session
from ..services import rate_limit

router = APIRouter(prefix="/api/demo", tags=["demo"])

# Deliberately the smaller, "actually matters first" set from the phased build plan —
# repeat-visit detection, deeper intent topics, etc. are explicitly deferred (see spec's
# "Roadmap: After Initial Deployment").
ALLOWED_EVENT_TYPES = {
    "demo_page_opened",
    "suggested_question_clicked",
    "conversation_started",
    "message_sent",
    "lead_cta_clicked",
    "video_started",
    "video_25",
    "video_50",
    "video_75",
    "video_completed",
}


class DemoEventInput(BaseModel):
    event_type: str
    session_id: str = ""
    metadata: dict = {}


@router.get("/config")
def demo_config():
    """Minimal public config for the demo page's video/booking CTA — deliberately
    separate from /api/business, which carries admin-only settings (webhook URLs,
    etc.) that must never be exposed on a page whose link gets sent to a prospect."""
    with db_session() as conn:
        row = conn.execute("SELECT booking_link FROM business WHERE id = 1").fetchone()
    return {
        "has_video": (DATA_DIR / "demo_video.mp4").exists(),
        "booking_link": (row["booking_link"] if row else "") or "",
    }


@router.post("/events")
def record_event(event: DemoEventInput, request: Request):
    if event.event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type. Allowed: {sorted(ALLOWED_EVENT_TYPES)}")
    if len(event.session_id) > 200:
        raise HTTPException(400, "session_id too long")

    client_key = f"demo-event:{request.client.host if request.client else 'unknown'}"
    if not rate_limit.check_burst_limit(client_key):
        raise HTTPException(429, "Too many requests — please try again in a minute")

    with db_session() as conn:
        conn.execute(
            "INSERT INTO demo_events (event_type, session_id, metadata, created_at) VALUES (?, ?, ?, ?)",
            (event.event_type, event.session_id, json.dumps(event.metadata)[:2000], datetime.now(timezone.utc).isoformat()),
        )
    return {"ok": True}


@router.get("/events/summary")
def events_summary():
    """Powers the dashboard's 'Demo engagement' card — see dashboard/app.js."""
    with db_session() as conn:
        rows = conn.execute("SELECT event_type, session_id, created_at FROM demo_events").fetchall()

    by_type = {}
    sessions_by_type = {}
    last_activity = None
    for r in rows:
        by_type[r["event_type"]] = by_type.get(r["event_type"], 0) + 1
        if r["session_id"]:
            sessions_by_type.setdefault(r["event_type"], set()).add(r["session_id"])
        if last_activity is None or r["created_at"] > last_activity:
            last_activity = r["created_at"]

    return {
        "total_opens": by_type.get("demo_page_opened", 0),
        "unique_sessions": len(sessions_by_type.get("demo_page_opened", set())),
        "conversations_started": by_type.get("conversation_started", 0),
        "messages_sent": by_type.get("message_sent", 0),
        "suggested_question_clicks": by_type.get("suggested_question_clicked", 0),
        "lead_cta_clicks": by_type.get("lead_cta_clicked", 0),
        "video_views": by_type.get("video_started", 0),
        "video_completions": by_type.get("video_completed", 0),
        "last_activity_at": last_activity,
        "has_any_events": len(rows) > 0,
    }
