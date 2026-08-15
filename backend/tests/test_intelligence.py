import json

from app import db
from app.services import intelligence


def _reset_db(tmp_path):
    db.DB_PATH = tmp_path / "test.db"
    db.init_db()
    intelligence.ensure_schema()


def test_settings_round_trip(tmp_path):
    _reset_db(tmp_path)
    saved = intelligence.save_settings({
        "enabled": True,
        "vertical": "personal_injury",
        "primary_jurisdiction": "TX",
        "additional_jurisdictions": ["OK"],
        "accepted_types": ["auto_accident"],
        "languages": ["English", "Spanish"],
        "scoring_rules": {"accepted_case_type": 10},
        "priority_thresholds": {"p1": 70, "p2": 45, "p3": 20},
    })
    assert saved["enabled"] is True
    assert saved["primary_jurisdiction"] == "TX"
    assert saved["additional_jurisdictions"] == ["OK"]
    assert saved["accepted_types"] == ["auto_accident"]


def test_processes_machine_readable_lead_intelligence(tmp_path):
    _reset_db(tmp_path)
    intelligence.save_settings({
        "enabled": True,
        "vertical": "personal_injury",
        "primary_jurisdiction": "TX",
        "scoring_rules": {
            "within_72_hours": 10,
            "active_treatment": 8,
            "requests_attorney_conversation": 10,
            "accepted_case_type": 10,
        },
        "priority_thresholds": {"p1": 30, "p2": 20, "p3": 10},
    })
    intelligence.create_routing_rule({
        "label": "Recent treatment priority",
        "condition": {"all_signals": ["within_72_hours", "active_treatment"]},
        "priority_override": "P1",
        "destination_label": "Urgent intake",
        "active": True,
        "position": 0,
    })

    payload = {
        "attributes": {
            "incident_type": "auto_accident",
            "incident_state": "TX",
            "treatment_status": "ER",
            "already_represented": False,
        },
        "signals": [
            "within_72_hours",
            "active_treatment",
            "requests_attorney_conversation",
            "accepted_case_type",
        ],
        "summary": "Recent auto collision with ER treatment; visitor requests attorney callback.",
    }
    notes = "Human-readable intake summary.\n[EIQ_INTEL]\n" + json.dumps(payload) + "\n[/EIQ_INTEL]"

    with db.db_session() as conn:
        conv = conn.execute(
            "INSERT INTO conversations (session_id, created_at) VALUES ('abc', '2026-08-09T00:00:00+00:00')"
        )
        lead = conn.execute(
            """INSERT INTO leads (conversation_id, name, phone, intent, notes, status, handoff_notified, created_at)
            VALUES (?, 'Maria', '5551234567', 'general_inquiry', ?, 'new', 0, '2026-08-09T00:00:01+00:00')""",
            (conv.lastrowid, notes),
        )
        lead_id = lead.lastrowid

    result = intelligence.process_lead(lead_id)
    assert result["processed"] is True
    assert result["priority_level"] == "P1"
    assert result["routing_destination"] == "Urgent intake"

    stored = intelligence.get_lead_intelligence(lead_id)
    assert stored["attributes"]["incident_state"] == "TX"
    assert stored["attributes"]["already_represented"] is False
    assert stored["intelligent_summary"].startswith("Recent auto collision")


def test_lead_without_payload_is_ignored(tmp_path):
    _reset_db(tmp_path)
    intelligence.save_settings({"enabled": True})
    with db.db_session() as conn:
        conv = conn.execute(
            "INSERT INTO conversations (session_id, created_at) VALUES ('plain', '2026-08-09T00:00:00+00:00')"
        )
        lead = conn.execute(
            """INSERT INTO leads (conversation_id, intent, notes, status, handoff_notified, created_at)
            VALUES (?, 'general_inquiry', 'ordinary legacy notes', 'new', 0, '2026-08-09T00:00:01+00:00')""",
            (conv.lastrowid,),
        )
        lead_id = lead.lastrowid
    result = intelligence.process_lead(lead_id)
    assert result == {"processed": False, "reason": "no_intelligence_payload"}
