from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import intelligence

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


class IntelligenceSettingsInput(BaseModel):
    enabled: bool = False
    vertical: str = ""
    primary_jurisdiction: str = ""
    additional_jurisdictions: list[str] = Field(default_factory=list)
    jurisdiction_mode: str = "single_state"
    approved_boundary_text: str = ""
    accepted_types: list[str] = Field(default_factory=list)
    excluded_types: list[str] = Field(default_factory=list)
    existing_representation_policy: str = ""
    out_of_area_policy: str = ""
    property_damage_only_policy: str = ""
    urgent_handoff_webhook_url: str = ""
    urgent_handoff_email: str = ""
    standard_handoff_webhook_url: str = ""
    standard_handoff_email: str = ""
    after_hours_behavior: str = "capture_and_notify"
    languages: list[str] = Field(default_factory=list)
    never_say_text: str = ""
    scoring_rules: dict[str, int] = Field(default_factory=dict)
    priority_thresholds: dict[str, int] = Field(default_factory=dict)


class RoutingRuleInput(BaseModel):
    label: str
    condition: dict[str, Any] = Field(default_factory=dict)
    priority_override: Optional[str] = None
    destination_label: str = ""
    handoff_webhook_url: str = ""
    handoff_email: str = ""
    visitor_message: str = ""
    active: bool = True
    position: int = 0


class DemoProfileInput(BaseModel):
    name: str
    vertical: str = ""
    jurisdiction: str = ""
    scenario: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/settings")
def get_settings():
    return intelligence.get_settings()


@router.put("/settings")
def put_settings(settings: IntelligenceSettingsInput):
    return intelligence.save_settings(settings.model_dump())


@router.get("/routing-rules")
def routing_rules():
    return intelligence.list_routing_rules()


@router.post("/routing-rules")
def add_routing_rule(rule: RoutingRuleInput):
    return intelligence.create_routing_rule(rule.model_dump())


@router.delete("/routing-rules/{rule_id}")
def delete_routing_rule(rule_id: int):
    intelligence.delete_routing_rule(rule_id)
    return {"ok": True}


@router.post("/leads/{lead_id}/process")
def process_lead(lead_id: int):
    result = intelligence.process_lead(lead_id)
    if result.get("reason") == "lead_not_found":
        raise HTTPException(404, "Lead not found")
    return result


@router.get("/leads")
def all_lead_intelligence():
    return intelligence.get_all_lead_intelligence()


@router.get("/leads/{lead_id}")
def lead_intelligence(lead_id: int):
    result = intelligence.get_lead_intelligence(lead_id)
    if result is None:
        raise HTTPException(404, "No intelligence record for this lead")
    return result


@router.get("/demo-profiles")
def list_demo_profiles():
    intelligence.ensure_schema()
    from ..db import db_session
    import json

    with db_session() as conn:
        rows = conn.execute("SELECT * FROM demo_profiles ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["config"] = json.loads(item.pop("config_json") or "{}")
        except json.JSONDecodeError:
            item["config"] = {}
        result.append(item)
    return result


@router.post("/demo-profiles")
def create_demo_profile(profile: DemoProfileInput):
    intelligence.ensure_schema()
    from ..db import db_session
    from datetime import datetime, timezone
    import json

    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO demo_profiles (name, vertical, jurisdiction, scenario, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (profile.name, profile.vertical, profile.jurisdiction, profile.scenario, json.dumps(profile.config), now, now),
        )
        row = conn.execute("SELECT * FROM demo_profiles WHERE id=?", (cur.lastrowid,)).fetchone()
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json") or "{}")
    return item
