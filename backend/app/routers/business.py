from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from datetime import datetime, timezone

from ..config import AGENCY_NOTIFY_EMAIL, AGENCY_NOTIFY_WEBHOOK_URL, PRODUCT_NAME
from ..db import db_session
from ..services import faq_matching, handoff, ingestion, rate_limit, seo

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
    monthly_message_limit: int = 500
    rot_aging_minutes: int = 1440
    rot_rotting_minutes: int = 4320
    pipeline_enabled: bool = False
    knowledge_source: str = ""


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    claimed_by: Optional[str] = None
    notes: Optional[str] = None
    good_to_know: Optional[str] = None
    outcome: Optional[str] = None


class ManualDocument(BaseModel):
    label: str
    text: str


class FaqInput(BaseModel):
    question: str
    answer: str
    category: str = ""
    priority: int = 0


class FactInput(BaseModel):
    label: str
    value: str


class SupportRequestInput(BaseModel):
    category: str
    details: str
    urgency: str = "normal"
    contact_info: str = ""
    screenshot_data_uri: Optional[str] = None


@router.get("/business")
def get_business():
    with db_session() as conn:
        row = conn.execute("SELECT * FROM business WHERE id = 1").fetchone()
    data = dict(row)
    data["messages_used_this_month"] = rate_limit.messages_used_this_month()
    data["product_name"] = PRODUCT_NAME
    return data


@router.put("/business")
def update_business(settings: BusinessSettings):
    if settings.rot_rotting_minutes < settings.rot_aging_minutes:
        raise HTTPException(400, "Rotting threshold must be equal to or later than the aging threshold")
    with db_session() as conn:
        conn.execute(
            """UPDATE business SET name=?, assistant_name=?, assistant_image_url=?, website_url=?,
               scheduling_link=?, handoff_webhook_url=?, handoff_email=?, flow_script=?, accent_color=?,
               monthly_message_limit=?, rot_aging_minutes=?, rot_rotting_minutes=?, pipeline_enabled=?,
               knowledge_source=? WHERE id=1""",
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
                settings.monthly_message_limit,
                settings.rot_aging_minutes,
                settings.rot_rotting_minutes,
                int(settings.pipeline_enabled),
                settings.knowledge_source,
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


@router.get("/knowledge/faqs")
def list_faqs():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM faqs ORDER BY priority DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/knowledge/faqs")
def add_faq(faq: FaqInput):
    if not faq.question.strip() or not faq.answer.strip():
        raise HTTPException(400, "Question and answer are both required")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO faqs (question, answer, category, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (faq.question, faq.answer, faq.category, faq.priority, now, now),
        )
        row = conn.execute("SELECT * FROM faqs WHERE id = ?", (cur.lastrowid,)).fetchone()
    faq_matching.rebuild_index()
    return dict(row)


@router.patch("/knowledge/faqs/{faq_id}")
def update_faq(faq_id: int, faq: FaqInput):
    if not faq.question.strip() or not faq.answer.strip():
        raise HTTPException(400, "Question and answer are both required")
    with db_session() as conn:
        conn.execute(
            "UPDATE faqs SET question=?, answer=?, category=?, priority=?, updated_at=? WHERE id=?",
            (faq.question, faq.answer, faq.category, faq.priority, datetime.now(timezone.utc).isoformat(), faq_id),
        )
        row = conn.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "FAQ not found")
    faq_matching.rebuild_index()
    return dict(row)


@router.delete("/knowledge/faqs/{faq_id}")
def delete_faq(faq_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    faq_matching.rebuild_index()
    return {"ok": True}


@router.get("/knowledge/facts")
def list_facts():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM business_facts ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


@router.post("/knowledge/facts")
def add_fact(fact: FactInput):
    if not fact.label.strip() or not fact.value.strip():
        raise HTTPException(400, "Label and value are both required")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO business_facts (label, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (fact.label, fact.value, now, now),
        )
        row = conn.execute("SELECT * FROM business_facts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.patch("/knowledge/facts/{fact_id}")
def update_fact(fact_id: int, fact: FactInput):
    if not fact.label.strip() or not fact.value.strip():
        raise HTTPException(400, "Label and value are both required")
    with db_session() as conn:
        conn.execute(
            "UPDATE business_facts SET label=?, value=?, updated_at=? WHERE id=?",
            (fact.label, fact.value, datetime.now(timezone.utc).isoformat(), fact_id),
        )
        row = conn.execute("SELECT * FROM business_facts WHERE id = ?", (fact_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Fact not found")
    return dict(row)


@router.delete("/knowledge/facts/{fact_id}")
def delete_fact(fact_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM business_facts WHERE id = ?", (fact_id,))
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


@router.post("/leads/{lead_id}/promote")
def promote_lead(lead_id: int):
    """Create a Pipeline card seeded from a claimed lead, linked back via source_lead_id, and
    mark the originating lead Done — its intake job is finished, the relationship continues
    in Pipeline now. Per BIA_configurable_pipeline_board.md."""
    with db_session() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise HTTPException(404, "Lead not found")
        first_stage = conn.execute("SELECT id FROM pipeline_stages ORDER BY position ASC LIMIT 1").fetchone()
        if first_stage is None:
            raise HTTPException(400, "No pipeline stages configured yet")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pipeline_cards WHERE stage_id = ?", (first_stage["id"],)
        ).fetchone()["n"]
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO pipeline_cards
               (stage_id, name, email, phone, source_lead_id, position, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (first_stage["id"], lead["name"], lead["email"], lead["phone"], lead_id, count, now, now),
        )
        conn.execute("UPDATE leads SET status = 'done' WHERE id = ?", (lead_id,))
        card = conn.execute("SELECT * FROM pipeline_cards WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(card)


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


@router.get("/usage/summary")
def usage_summary():
    month_start = rate_limit.month_start_iso()
    with db_session() as conn:
        totals = conn.execute(
            """SELECT COUNT(*) AS assistant_messages,
                      COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                      COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                      COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
               FROM messages WHERE role = 'assistant' AND created_at >= ? AND latency_ms IS NOT NULL""",
            (month_start,),
        ).fetchone()
        faq_count = conn.execute("SELECT COUNT(*) AS c FROM faqs").fetchone()["c"]
        facts_count = conn.execute("SELECT COUNT(*) AS c FROM business_facts").fetchone()["c"]
        source_count = conn.execute("SELECT COUNT(*) AS c FROM sources").fetchone()["c"]
        gaps = conn.execute(
            """SELECT id, notes, created_at FROM leads
               WHERE intent = 'unresolved_question' AND created_at >= ?
               ORDER BY id DESC LIMIT 50""",
            (month_start,),
        ).fetchall()
        gaps_count_all_time = conn.execute(
            "SELECT COUNT(*) AS c FROM leads WHERE intent = 'unresolved_question'"
        ).fetchone()["c"]

    return {
        "messages_used_this_month": rate_limit.messages_used_this_month(),
        "assistant_messages_this_month": totals["assistant_messages"],
        "total_input_tokens": totals["total_input_tokens"],
        "total_output_tokens": totals["total_output_tokens"],
        "avg_latency_ms": round(totals["avg_latency_ms"]) if totals["avg_latency_ms"] else 0,
        "faq_count": faq_count,
        "facts_count": facts_count,
        "source_count": source_count,
        "knowledge_gaps_this_month": [dict(g) for g in gaps],
        "knowledge_gaps_all_time_count": gaps_count_all_time,
    }


@router.get("/seo/faq-schema")
def faq_schema():
    return seo.generate_faq_schema()


@router.get("/seo/ai-crawler-access")
def ai_crawler_access():
    with db_session() as conn:
        row = conn.execute("SELECT website_url FROM business WHERE id = 1").fetchone()
    website_url = row["website_url"] if row else ""
    if not website_url:
        return {"checked": False, "results": [], "message": "Set a website URL in Settings first."}
    results = seo.check_ai_crawler_access(website_url)
    return {"checked": True, "results": results}


@router.post("/support-request")
def submit_support_request(req: SupportRequestInput):
    if not req.category.strip() or not req.details.strip():
        raise HTTPException(400, "Category and details are both required")
    with db_session() as conn:
        business = conn.execute("SELECT name FROM business WHERE id = 1").fetchone()
    business_name = business["name"] if business else "a client"

    # The raw image isn't sent through the webhook itself — payload size limits on
    # Slack/Zapier-style endpoints make that risky. It's stored on the request record;
    # the notification just flags that one's attached.
    notified = handoff.notify(
        AGENCY_NOTIFY_WEBHOOK_URL,
        business_name,
        {
            "intent": "support_request",
            "name": business_name,
            "notes": f"[{req.category}] {req.details}"
            + (f" (contact: {req.contact_info})" if req.contact_info else "")
            + (" [screenshot attached — see request record]" if req.screenshot_data_uri else ""),
        },
        notify_email=AGENCY_NOTIFY_EMAIL,
    )
    with db_session() as conn:
        conn.execute(
            "INSERT INTO support_requests "
            "(category, details, urgency, contact_info, screenshot_data_uri, notified, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                req.category,
                req.details,
                req.urgency,
                req.contact_info,
                req.screenshot_data_uri,
                1 if notified else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return {"ok": True, "notified": notified}


@router.get("/support-requests")
def list_support_requests():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM support_requests ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


SUPPORT_REQUEST_STATUSES = {"new", "in_progress", "resolved"}


class SupportRequestStatusUpdate(BaseModel):
    status: str


@router.patch("/support-requests/{request_id}")
def update_support_request_status(request_id: int, update: SupportRequestStatusUpdate):
    if update.status not in SUPPORT_REQUEST_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(SUPPORT_REQUEST_STATUSES)}")
    with db_session() as conn:
        conn.execute("UPDATE support_requests SET status = ? WHERE id = ?", (update.status, request_id))
        row = conn.execute("SELECT * FROM support_requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Support request not found")
    return dict(row)
