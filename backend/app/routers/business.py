from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..db import db_session
from ..services import ingestion

LEAD_STATUSES = {"new", "claimed", "done"}
LEAD_OUTCOMES = {"booked", "not_interested", "no_response", "duplicate", "spam", "other"}

router = APIRouter(prefix="/api", tags=["business"])


class BusinessSettings(BaseModel):
    name: str
    assistant_name: str = ""
    assistant_image_url: str = ""
    website_url: str = ""
    scheduling_link: str = ""
    handoff_webhook_url: str = ""
    handoff_email: str = ""
    flow_script: str = ""
    accent_color: str = "#4f46e5"


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    claimed_by: Optional[str] = None
    notes: Optional[str] = None
    good_to_know: Optional[str] = None
    outcome: Optional[str] = None


class ManualDocument(BaseModel):
    label: str
    text: str


@router.get("/business")
def get_business():
    with db_session() as conn:
        row = conn.execute("SELECT * FROM business WHERE id = 1").fetchone()
    return dict(row)


@router.put("/business")
def update_business(settings: BusinessSettings):
    with db_session() as conn:
        conn.execute(
            """UPDATE business SET name=?, assistant_name=?, assistant_image_url=?, website_url=?,
               scheduling_link=?, handoff_webhook_url=?, handoff_email=?, flow_script=?, accent_color=? WHERE id=1""",
            (
                settings.name,
                settings.assistant_name,
                settings.assistant_image_url,
                settings.website_url,
                settings.scheduling_link,
                settings.handoff_webhook_url,
                settings.handoff_email,
                settings.flow_script,
                settings.accent_color,
            ),
        )
    return {"ok": True}


@router.post("/knowledge/crawl")
def trigger_crawl(background_tasks: BackgroundTasks):
    with db_session() as conn:
        row = conn.execute("SELECT website_url FROM business WHERE id = 1").fetchone()
    url = row["website_url"] if row else ""
    if not url:
        raise HTTPException(400, "Set a website_url first via PUT /api/business")
    background_tasks.add_task(ingestion.crawl_site, url)
    return {"status": "crawling_started", "url": url}


@router.post("/knowledge/documents")
def add_document(doc: ManualDocument):
    if not doc.text.strip():
        raise HTTPException(400, "Document text is empty")
    return ingestion.add_manual_document(doc.label or "Untitled document", doc.text)


@router.get("/knowledge/sources")
def sources():
    return ingestion.list_sources()


@router.delete("/knowledge/sources/{source_id}")
def delete_source(source_id: int):
    ingestion.delete_source(source_id)
    return {"ok": True}


@router.get("/leads")
def list_leads():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, update: LeadUpdate):
    if update.status is not None and update.status not in LEAD_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(LEAD_STATUSES)}")
    if update.outcome is not None and update.outcome not in LEAD_OUTCOMES:
        raise HTTPException(400, f"outcome must be one of {sorted(LEAD_OUTCOMES)}")

    fields, values = [], []
    if update.status is not None:
        fields.append("status = ?")
        values.append(update.status)
    if update.claimed_by is not None:
        fields.append("claimed_by = ?")
        values.append(update.claimed_by)
    if update.notes is not None:
        fields.append("notes = ?")
        values.append(update.notes)
    if update.good_to_know is not None:
        fields.append("good_to_know = ?")
        values.append(update.good_to_know)
    if update.outcome is not None:
        fields.append("outcome = ?")
        values.append(update.outcome)

    if not fields:
        raise HTTPException(400, "Nothing to update")

    values.append(lead_id)
    with db_session() as conn:
        conn.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Lead not found")
    return dict(row)


@router.get("/conversations")
def list_conversations(q: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
    where, params = [], []
    if since:
        where.append("c.created_at >= ?")
        params.append(since)
    if until:
        # `until` is a date (YYYY-MM-DD) from a date-picker; make it inclusive of the whole day.
        where.append("c.created_at <= ?")
        params.append(until + "T23:59:59")
    if q:
        where.append(
            "(c.session_id LIKE ? OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.content LIKE ?))"
        )
        like = f"%{q}%"
        params.extend([like, like])

    sql = """SELECT c.id, c.session_id, c.created_at,
                    (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
             FROM conversations c"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.id DESC LIMIT 200"

    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]
