from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

from ..db import db_session
from . import handoff

logger = logging.getLogger(__name__)

INTEL_RE = re.compile(r"\[EIQ_INTEL\](.*?)\[/EIQ_INTEL\]", re.DOTALL)

DEFAULT_SCORING_RULES = {
    "fatality": 25,
    "major_surgery_or_hospitalization": 20,
    "significant_injury": 15,
    "active_treatment": 8,
    "commercial_truck": 15,
    "commercial_vehicle": 10,
    "pedestrian_or_motorcycle": 8,
    "child_involved": 10,
    "police_or_incident_report": 5,
    "photos_or_video": 3,
    "witnesses": 3,
    "within_72_hours": 10,
    "within_30_days": 7,
    "requests_attorney_conversation": 10,
    "provides_contact_info": 5,
    "requests_consultation": 8,
    "inside_jurisdiction": 10,
    "accepted_case_type": 10,
}

DEFAULT_PRIORITY_THRESHOLDS = {"p1": 70, "p2": 45, "p3": 20}


def ensure_schema() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS intelligence_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                vertical TEXT NOT NULL DEFAULT '',
                primary_jurisdiction TEXT NOT NULL DEFAULT '',
                additional_jurisdictions_json TEXT NOT NULL DEFAULT '[]',
                jurisdiction_mode TEXT NOT NULL DEFAULT 'single_state',
                approved_boundary_text TEXT NOT NULL DEFAULT '',
                accepted_types_json TEXT NOT NULL DEFAULT '[]',
                excluded_types_json TEXT NOT NULL DEFAULT '[]',
                existing_representation_policy TEXT NOT NULL DEFAULT '',
                out_of_area_policy TEXT NOT NULL DEFAULT '',
                property_damage_only_policy TEXT NOT NULL DEFAULT '',
                urgent_handoff_webhook_url TEXT NOT NULL DEFAULT '',
                urgent_handoff_email TEXT NOT NULL DEFAULT '',
                standard_handoff_webhook_url TEXT NOT NULL DEFAULT '',
                standard_handoff_email TEXT NOT NULL DEFAULT '',
                after_hours_behavior TEXT NOT NULL DEFAULT 'capture_and_notify',
                languages_json TEXT NOT NULL DEFAULT '[]',
                never_say_text TEXT NOT NULL DEFAULT '',
                scoring_rules_json TEXT NOT NULL DEFAULT '{}',
                priority_thresholds_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS routing_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                condition_json TEXT NOT NULL DEFAULT '{}',
                priority_override TEXT,
                destination_label TEXT NOT NULL DEFAULT '',
                handoff_webhook_url TEXT NOT NULL DEFAULT '',
                handoff_email TEXT NOT NULL DEFAULT '',
                visitor_message TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lead_attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                value TEXT,
                value_type TEXT NOT NULL DEFAULT 'string',
                created_at TEXT NOT NULL,
                UNIQUE(lead_id, key)
            );

            CREATE TABLE IF NOT EXISTS lead_intelligence (
                lead_id INTEGER PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
                priority_score INTEGER NOT NULL DEFAULT 0,
                priority_level TEXT NOT NULL DEFAULT 'P4',
                routing_destination TEXT NOT NULL DEFAULT '',
                routing_reason TEXT NOT NULL DEFAULT '',
                intelligent_summary TEXT NOT NULL DEFAULT '',
                signals_json TEXT NOT NULL DEFAULT '[]',
                unrecognized_signals_json TEXT NOT NULL DEFAULT '[]',
                processed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS demo_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                vertical TEXT NOT NULL DEFAULT '',
                jurisdiction TEXT NOT NULL DEFAULT '',
                scenario TEXT NOT NULL DEFAULT '',
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        row = conn.execute("SELECT id FROM intelligence_settings WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO intelligence_settings (id, scoring_rules_json, priority_thresholds_json, updated_at) VALUES (1, ?, ?, ?)",
                (json.dumps(DEFAULT_SCORING_RULES), json.dumps(DEFAULT_PRIORITY_THRESHOLDS), _now()),
            )
        try:
            conn.execute("ALTER TABLE lead_intelligence ADD COLUMN unrecognized_signals_json TEXT NOT NULL DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # column already exists


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str, fallback):
    try:
        return json.loads(value or "")
    except (json.JSONDecodeError, TypeError):
        return fallback


def get_settings() -> dict:
    ensure_schema()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM intelligence_settings WHERE id = 1").fetchone()
    data = dict(row)
    for field in (
        "additional_jurisdictions_json",
        "accepted_types_json",
        "excluded_types_json",
        "languages_json",
        "scoring_rules_json",
        "priority_thresholds_json",
    ):
        data[field.removesuffix("_json")] = _loads(data.pop(field), [] if field.endswith("s_json") and field not in ("scoring_rules_json", "priority_thresholds_json") else {})
    data["enabled"] = bool(data["enabled"])
    return data


def save_settings(payload: dict) -> dict:
    ensure_schema()
    fields = {
        "enabled": int(bool(payload.get("enabled", False))),
        "vertical": payload.get("vertical", ""),
        "primary_jurisdiction": payload.get("primary_jurisdiction", ""),
        "additional_jurisdictions_json": json.dumps(payload.get("additional_jurisdictions", [])),
        "jurisdiction_mode": payload.get("jurisdiction_mode", "single_state"),
        "approved_boundary_text": payload.get("approved_boundary_text", ""),
        "accepted_types_json": json.dumps(payload.get("accepted_types", [])),
        "excluded_types_json": json.dumps(payload.get("excluded_types", [])),
        "existing_representation_policy": payload.get("existing_representation_policy", ""),
        "out_of_area_policy": payload.get("out_of_area_policy", ""),
        "property_damage_only_policy": payload.get("property_damage_only_policy", ""),
        "urgent_handoff_webhook_url": payload.get("urgent_handoff_webhook_url", ""),
        "urgent_handoff_email": payload.get("urgent_handoff_email", ""),
        "standard_handoff_webhook_url": payload.get("standard_handoff_webhook_url", ""),
        "standard_handoff_email": payload.get("standard_handoff_email", ""),
        "after_hours_behavior": payload.get("after_hours_behavior", "capture_and_notify"),
        "languages_json": json.dumps(payload.get("languages", [])),
        "never_say_text": payload.get("never_say_text", ""),
        "scoring_rules_json": json.dumps(payload.get("scoring_rules") or DEFAULT_SCORING_RULES),
        "priority_thresholds_json": json.dumps(payload.get("priority_thresholds") or DEFAULT_PRIORITY_THRESHOLDS),
        "updated_at": _now(),
    }
    sql = "UPDATE intelligence_settings SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=1"
    with db_session() as conn:
        conn.execute(sql, list(fields.values()))
    return get_settings()


def list_routing_rules() -> list[dict]:
    ensure_schema()
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM routing_rules ORDER BY position ASC, id ASC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["condition"] = _loads(item.pop("condition_json"), {})
        item["active"] = bool(item["active"])
        result.append(item)
    return result


def create_routing_rule(payload: dict) -> dict:
    ensure_schema()
    now = _now()
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO routing_rules
            (label, condition_json, priority_override, destination_label, handoff_webhook_url,
             handoff_email, visitor_message, active, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.get("label", "Routing rule"),
                json.dumps(payload.get("condition", {})),
                payload.get("priority_override"),
                payload.get("destination_label", ""),
                payload.get("handoff_webhook_url", ""),
                payload.get("handoff_email", ""),
                payload.get("visitor_message", ""),
                int(bool(payload.get("active", True))),
                int(payload.get("position", 0)),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM routing_rules WHERE id=?", (cur.lastrowid,)).fetchone()
    result = dict(row)
    result["condition"] = _loads(result.pop("condition_json"), {})
    result["active"] = bool(result["active"])
    return result


def delete_routing_rule(rule_id: int) -> None:
    ensure_schema()
    with db_session() as conn:
        conn.execute("DELETE FROM routing_rules WHERE id=?", (rule_id,))


def _extract_intel(notes: str) -> dict | None:
    match = INTEL_RE.search(notes or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _serialize_value(value):
    if isinstance(value, bool):
        return ("true" if value else "false", "boolean")
    if isinstance(value, (int, float)):
        return (str(value), "number")
    if isinstance(value, (list, dict)):
        return (json.dumps(value), "json")
    if value is None:
        return ("", "null")
    return (str(value), "string")


def _matches(condition: dict, attributes: dict, signals: set[str], priority_level: str) -> bool:
    if not condition:
        return True
    any_signal = condition.get("any_signal") or []
    if any_signal and not any(s in signals for s in any_signal):
        return False
    all_signals = condition.get("all_signals") or []
    if all_signals and not all(s in signals for s in all_signals):
        return False
    levels = condition.get("priority_level_in") or []
    if levels and priority_level not in levels:
        return False
    equals = condition.get("attributes_equal") or {}
    for key, expected in equals.items():
        if attributes.get(key) != expected:
            return False
    return True


def _priority_from_score(score: int, thresholds: dict) -> str:
    if score >= int(thresholds.get("p1", 70)):
        return "P1"
    if score >= int(thresholds.get("p2", 45)):
        return "P2"
    if score >= int(thresholds.get("p3", 20)):
        return "P3"
    return "P4"


def process_lead(lead_id: int) -> dict:
    ensure_schema()
    settings = get_settings()
    with db_session() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        business = conn.execute("SELECT * FROM business WHERE id=1").fetchone()
    if lead is None:
        return {"processed": False, "reason": "lead_not_found"}
    if not settings.get("enabled"):
        return {"processed": False, "reason": "intelligence_disabled"}

    payload = _extract_intel(lead["notes"] or "")
    if not payload:
        return {"processed": False, "reason": "no_intelligence_payload"}

    attributes = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {}
    raw_signals = {str(s) for s in (payload.get("signals") or [])}
    summary = str(payload.get("summary") or "").strip()

    scoring = settings.get("scoring_rules") or DEFAULT_SCORING_RULES
    # The model only ever produces reliable scores/routing for signal names in the approved
    # vocabulary (scoring_rules keys, which mirror each BIP's documented signal list). A
    # near-miss synonym ("hospitalization" instead of "major_surgery_or_hospitalization")
    # would otherwise silently score 0 and fail to match any routing rule — exactly the kind
    # of failure that looks like a low-priority lead when it's actually the opposite. Split
    # signals into recognized (used for scoring/routing) and unrecognized (logged and stored
    # for review, never silently dropped) instead of trusting the model's naming outright.
    known_signals = set(DEFAULT_SCORING_RULES.keys()) | set(scoring.keys())
    signals = raw_signals & known_signals
    unrecognized_signals = raw_signals - known_signals
    if unrecognized_signals:
        logger.warning(
            "Lead %s: intelligence payload used %d unrecognized signal(s) not in the approved "
            "vocabulary — they scored 0 and could not match routing rules: %s",
            lead_id,
            len(unrecognized_signals),
            sorted(unrecognized_signals),
        )

    score = sum(int(scoring.get(signal, 0)) for signal in signals)
    thresholds = settings.get("priority_thresholds") or DEFAULT_PRIORITY_THRESHOLDS
    priority_level = _priority_from_score(score, thresholds)

    routing_reason = ", ".join(sorted(signals))[:1000]
    destination_label = ""
    selected_rule = None
    for rule in list_routing_rules():
        if rule["active"] and _matches(rule["condition"], attributes, signals, priority_level):
            selected_rule = rule
            if rule.get("priority_override"):
                priority_level = rule["priority_override"]
            destination_label = rule.get("destination_label") or rule.get("label") or ""
            routing_reason = f"Matched routing rule: {rule.get('label', '')}"
            break

    now = _now()
    with db_session() as conn:
        for key, value in attributes.items():
            serialized, value_type = _serialize_value(value)
            conn.execute(
                """INSERT INTO lead_attributes (lead_id, key, value, value_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lead_id, key) DO UPDATE SET value=excluded.value, value_type=excluded.value_type""",
                (lead_id, str(key), serialized, value_type, now),
            )
        conn.execute(
            """INSERT INTO lead_intelligence
            (lead_id, priority_score, priority_level, routing_destination, routing_reason,
             intelligent_summary, signals_json, unrecognized_signals_json, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET
                priority_score=excluded.priority_score,
                priority_level=excluded.priority_level,
                routing_destination=excluded.routing_destination,
                routing_reason=excluded.routing_reason,
                intelligent_summary=excluded.intelligent_summary,
                signals_json=excluded.signals_json,
                unrecognized_signals_json=excluded.unrecognized_signals_json,
                processed_at=excluded.processed_at""",
            (
                lead_id, score, priority_level, destination_label, routing_reason, summary,
                json.dumps(sorted(signals)), json.dumps(sorted(unrecognized_signals)), now,
            ),
        )

    route_webhook = ""
    route_email = ""
    if selected_rule:
        route_webhook = selected_rule.get("handoff_webhook_url") or ""
        route_email = selected_rule.get("handoff_email") or ""
    elif priority_level == "P1":
        route_webhook = settings.get("urgent_handoff_webhook_url") or ""
        route_email = settings.get("urgent_handoff_email") or ""
    else:
        route_webhook = settings.get("standard_handoff_webhook_url") or ""
        route_email = settings.get("standard_handoff_email") or ""

    routed = False
    if route_webhook or route_email:
        routed = handoff.notify(
            route_webhook,
            business["name"] if business else "your business",
            {
                "intent": lead["intent"],
                "name": lead["name"],
                "email": lead["email"],
                "phone": lead["phone"],
                "priority_level": priority_level,
                "priority_score": score,
                "routing_destination": destination_label,
                "summary": summary,
                "attributes": attributes,
                "signals": sorted(signals),
            },
            notify_email=route_email,
        )

    return {
        "processed": True,
        "lead_id": lead_id,
        "priority_score": score,
        "priority_level": priority_level,
        "routing_destination": destination_label,
        "routing_reason": routing_reason,
        "unrecognized_signals": sorted(unrecognized_signals),
        "routed": routed,
    }


def process_latest_lead_for_session(session_id: str) -> dict:
    ensure_schema()
    with db_session() as conn:
        row = conn.execute(
            """SELECT l.id
            FROM leads l
            JOIN conversations c ON c.id=l.conversation_id
            WHERE c.session_id=?
            ORDER BY l.id DESC LIMIT 1""",
            (session_id,),
        ).fetchone()
    if row is None:
        return {"processed": False, "reason": "no_lead"}
    with db_session() as conn:
        existing = conn.execute("SELECT lead_id FROM lead_intelligence WHERE lead_id=?", (row["id"],)).fetchone()
    if existing:
        return {"processed": False, "reason": "already_processed", "lead_id": row["id"]}
    return process_lead(row["id"])


def get_lead_intelligence(lead_id: int) -> dict | None:
    ensure_schema()
    with db_session() as conn:
        intel = conn.execute("SELECT * FROM lead_intelligence WHERE lead_id=?", (lead_id,)).fetchone()
        attrs = conn.execute("SELECT key, value, value_type FROM lead_attributes WHERE lead_id=? ORDER BY id", (lead_id,)).fetchall()
    if intel is None:
        return None
    result = dict(intel)
    result["signals"] = _loads(result.pop("signals_json"), [])
    result["unrecognized_signals"] = _loads(result.pop("unrecognized_signals_json", "[]"), [])
    result["attributes"] = {r["key"]: _deserialize_attr(r["value"], r["value_type"]) for r in attrs}
    return result


def get_all_lead_intelligence() -> dict[str, dict]:
    """Bulk read for dashboard lead-card surfacing — one query instead of N+1 per lead."""
    ensure_schema()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT lead_id, priority_score, priority_level, routing_destination, "
            "intelligent_summary, signals_json, unrecognized_signals_json FROM lead_intelligence"
        ).fetchall()
    result = {}
    for row in rows:
        item = dict(row)
        item["signals"] = _loads(item.pop("signals_json"), [])
        item["unrecognized_signals"] = _loads(item.pop("unrecognized_signals_json", "[]"), [])
        result[str(item["lead_id"])] = item
    return result


def _deserialize_attr(value: str, value_type: str):
    if value_type == "boolean":
        return value == "true"
    if value_type == "number":
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return value
    if value_type == "json":
        return _loads(value, value)
    if value_type == "null":
        return None
    return value
