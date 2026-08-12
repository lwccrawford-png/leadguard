#!/usr/bin/env python3
"""One-time import of the "Leadguard Outbound - Prospecting Sheet" into
ops/outreach.db's prospects table (see ops/outreach_db.py). Going forward the
spreadsheet is a historical snapshot only — all edits happen in the Outreach
CRM at /outreach.

Idempotent: matches existing rows by company_name (case-insensitive) and
skips them rather than duplicating, so it's safe to re-run.

Usage:
    venv/bin/python3 import_outreach_prospects.py [path/to/export.json]

Expects a JSON array of row dicts keyed by the sheet's own column headers
(what you get from exporting the sheet to CSV and loading it with
csv.DictReader — see the column mapping below for the exact headers
expected). Defaults to ops/outreach_prospects_export.json.
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

import outreach_db

DEFAULT_EXPORT_PATH = pathlib.Path(__file__).parent / "outreach_prospects_export.json"


def _int_or_none(s):
    s = (s or "").strip()
    return int(s) if s.isdigit() else None


def _questions(s):
    return [q.strip() for q in (s or "").split("\n") if q.strip()]


def row_to_prospect(row: dict) -> dict:
    return {
        "vertical": row.get("Vertical", "").strip(),
        "priority_rank": _int_or_none(row.get("Priority Rank")),
        "score": _int_or_none(row.get("Prospect Score /100")),
        "company_name": row.get("Company/Firm", "").strip(),
        "city_metro": row.get("City/Metro", "").strip(),
        "website": row.get("Website", "").strip(),
        "review_signal": row.get("Google/Review Signal (where verifiable)", "").strip(),
        "size_signal": row.get("Estimated Size Signal (publicly observable)", "").strip(),
        "primary_service": row.get("Primary Service/Practice Focus", "").strip(),
        "lead_leakage": row.get("Visible Lead Leakage / Intake Gap", "").strip(),
        "evidence": row.get("Exact Evidence/Observation", "").strip(),
        "personalization_hook": row.get("Best Personalization Hook", "").strip(),
        "demo_scenario": row.get("Suggested 60-90 sec Demo Scenario", "").strip(),
        "demo_questions": json.dumps(_questions(row.get("Suggested 3 Demo Questions"))),
        "decision_maker_name": row.get("Decision-Maker/Owner/Managing Partner name if publicly verifiable", "").strip(),
        "decision_maker_role": row.get("Decision-Maker Role", "").strip(),
        "phone": row.get("Public business phone", "").strip(),
        "email_or_contact_url": row.get("Public business email/contact URL if available", "").strip(),
        "linkedin": row.get("LinkedIn URL/profile search note if available", "").strip(),
        "facebook": row.get("Facebook", "").strip(),
        "instagram": row.get("Instagram", "").strip(),
        "preferred_channel": row.get("Preferred First Channel", "").strip(),
        "outreach_angle": row.get("Outreach Message Angle", "").strip(),
        "slug_suggestion": row.get("Demo URL Slug suggestion", "").strip(),
        "assigned_rep": row.get("Assigned Rep", "").strip(),
        "notes": row.get("Notes", "").strip(),
        "source_urls": row.get("Source URLs / Citation Notes", "").strip(),
        "status": row.get("Status", "").strip() or "Not Started",
    }


def main():
    export_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXPORT_PATH
    if not export_path.exists():
        print(f"No export file at {export_path}")
        sys.exit(1)

    rows = json.loads(export_path.read_text())
    now = datetime.now(timezone.utc).isoformat()

    inserted, skipped = 0, 0
    with outreach_db.db_session() as conn:
        existing_names = {
            r["company_name"].strip().lower()
            for r in conn.execute("SELECT company_name FROM prospects").fetchall()
        }
        for row in rows:
            p = row_to_prospect(row)
            if not p["company_name"]:
                continue
            if p["company_name"].strip().lower() in existing_names:
                skipped += 1
                continue
            p["cadence_step"] = 1
            p["last_touch_at"] = None
            p["next_touch_at"] = now  # nothing done yet — immediately actionable
            p["client_id"] = None
            p["demo_url"] = None
            p["created_at"] = now
            p["updated_at"] = now
            columns = ", ".join(p.keys())
            placeholders = ", ".join("?" for _ in p)
            conn.execute(f"INSERT INTO prospects ({columns}) VALUES ({placeholders})", tuple(p.values()))
            existing_names.add(p["company_name"].strip().lower())
            inserted += 1

    print(f"Imported {inserted} new prospects, skipped {skipped} already present.")


if __name__ == "__main__":
    main()
