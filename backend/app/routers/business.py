from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..db import db_session
from ..services import ingestion

router = APIRouter(prefix="/api", tags=["business"])


class BusinessSettings(BaseModel):
    name: str
    website_url: str = ""
    scheduling_link: str = ""
    handoff_webhook_url: str = ""
    flow_script: str = ""
    accent_color: str = "#4f46e5"


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
            """UPDATE business SET name=?, website_url=?, scheduling_link=?, handoff_webhook_url=?,
               flow_script=?, accent_color=? WHERE id=1""",
            (
                settings.name,
                settings.website_url,
                settings.scheduling_link,
                settings.handoff_webhook_url,
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


@router.get("/conversations")
def list_conversations():
    with db_session() as conn:
        rows = conn.execute(
            """SELECT c.id, c.session_id, c.created_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
               FROM conversations c ORDER BY c.id DESC LIMIT 200"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]
