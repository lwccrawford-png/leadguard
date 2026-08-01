from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import db_session

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

MAX_STAGES = 8


class StageInput(BaseModel):
    label: str
    notes_enabled: bool = False
    is_won: bool = False


class StageUpdate(BaseModel):
    label: Optional[str] = None
    notes_enabled: Optional[bool] = None
    is_won: Optional[bool] = None
    position: Optional[int] = None


class DropdownOptionInput(BaseModel):
    label: str


class CardInput(BaseModel):
    stage_id: int
    name: str = ""
    email: str = ""
    phone: str = ""


class CardUpdate(BaseModel):
    stage_id: Optional[int] = None
    notes: Optional[str] = None
    outcome_notes: Optional[str] = None
    chosen_option_id: Optional[int] = None
    claimed_by: Optional[str] = None
    position: Optional[int] = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _stage_with_options(conn, stage_row):
    stage = dict(stage_row)
    if stage["is_won"]:
        opts = conn.execute(
            "SELECT * FROM pipeline_dropdown_options WHERE stage_id = ? ORDER BY position ASC", (stage["id"],)
        ).fetchall()
        stage["dropdown_options"] = [dict(o) for o in opts]
    else:
        stage["dropdown_options"] = []
    return stage


@router.get("/stages")
def list_stages():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM pipeline_stages ORDER BY position ASC").fetchall()
        return [_stage_with_options(conn, r) for r in rows]


@router.post("/stages")
def create_stage(stage: StageInput):
    with db_session() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM pipeline_stages").fetchone()["n"]
        if count >= MAX_STAGES:
            raise HTTPException(400, f"Only {MAX_STAGES} stages allowed")
        if stage.is_won:
            existing_won = conn.execute("SELECT id FROM pipeline_stages WHERE is_won = 1").fetchone()
            if existing_won:
                raise HTTPException(400, "Only one stage can be marked as Won — unmark the existing one first")
        cur = conn.execute(
            "INSERT INTO pipeline_stages (label, position, notes_enabled, is_won, created_at) VALUES (?, ?, ?, ?, ?)",
            (stage.label, count, int(stage.notes_enabled), int(stage.is_won), _now()),
        )
        row = conn.execute("SELECT * FROM pipeline_stages WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _stage_with_options(conn, row)


@router.patch("/stages/{stage_id}")
def update_stage(stage_id: int, update: StageUpdate):
    with db_session() as conn:
        existing = conn.execute("SELECT * FROM pipeline_stages WHERE id = ?", (stage_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Stage not found")
        if update.is_won:
            other_won = conn.execute(
                "SELECT id FROM pipeline_stages WHERE is_won = 1 AND id != ?", (stage_id,)
            ).fetchone()
            if other_won:
                raise HTTPException(400, "Only one stage can be marked as Won — unmark the existing one first")
        fields = update.model_dump(exclude_unset=True)
        if not fields:
            return _stage_with_options(conn, existing)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        conn.execute(f"UPDATE pipeline_stages SET {set_clause} WHERE id = ?", (*values, stage_id))
        row = conn.execute("SELECT * FROM pipeline_stages WHERE id = ?", (stage_id,)).fetchone()
        return _stage_with_options(conn, row)


@router.delete("/stages/{stage_id}")
def delete_stage(stage_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM pipeline_stages WHERE id = ?", (stage_id,))
    return {"ok": True}


@router.post("/stages/{stage_id}/dropdown-options")
def add_dropdown_option(stage_id: int, option: DropdownOptionInput):
    with db_session() as conn:
        stage = conn.execute("SELECT * FROM pipeline_stages WHERE id = ?", (stage_id,)).fetchone()
        if not stage:
            raise HTTPException(404, "Stage not found")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pipeline_dropdown_options WHERE stage_id = ?", (stage_id,)
        ).fetchone()["n"]
        cur = conn.execute(
            "INSERT INTO pipeline_dropdown_options (stage_id, label, position) VALUES (?, ?, ?)",
            (stage_id, option.label, count),
        )
        row = conn.execute("SELECT * FROM pipeline_dropdown_options WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


@router.delete("/dropdown-options/{option_id}")
def delete_dropdown_option(option_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM pipeline_dropdown_options WHERE id = ?", (option_id,))
    return {"ok": True}


@router.get("/cards")
def list_cards():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM pipeline_cards ORDER BY position ASC, id ASC").fetchall()
        return [dict(r) for r in rows]


@router.post("/cards")
def create_card(card: CardInput):
    with db_session() as conn:
        stage = conn.execute("SELECT id FROM pipeline_stages WHERE id = ?", (card.stage_id,)).fetchone()
        if not stage:
            raise HTTPException(400, "Unknown stage_id")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pipeline_cards WHERE stage_id = ?", (card.stage_id,)
        ).fetchone()["n"]
        now = _now()
        cur = conn.execute(
            """INSERT INTO pipeline_cards (stage_id, name, email, phone, position, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (card.stage_id, card.name, card.email, card.phone, count, now, now),
        )
        row = conn.execute("SELECT * FROM pipeline_cards WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


@router.patch("/cards/{card_id}")
def update_card(card_id: int, update: CardUpdate):
    with db_session() as conn:
        existing = conn.execute("SELECT * FROM pipeline_cards WHERE id = ?", (card_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Card not found")
        fields = update.model_dump(exclude_unset=True)
        if not fields:
            return dict(existing)
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE pipeline_cards SET {set_clause} WHERE id = ?", (*fields.values(), card_id))
        row = conn.execute("SELECT * FROM pipeline_cards WHERE id = ?", (card_id,)).fetchone()
        return dict(row)


@router.delete("/cards/{card_id}")
def delete_card(card_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM pipeline_cards WHERE id = ?", (card_id,))
    return {"ok": True}
