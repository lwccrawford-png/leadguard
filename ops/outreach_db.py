"""Outreach CRM storage — the agency's own outbound prospect list, sales-cadence
tracking, and script library. Deliberately separate from clients.json (which
represents *provisioned running instances*) and from any per-client backend DB
(which is business-scoped and single-tenant, per CLAUDE.md) — a prospect here
may not have a demo instance yet at all.

Same conventions as backend/app/db.py: sqlite3.Row rows, CREATE TABLE IF NOT
EXISTS + best-effort ALTER TABLE migrations, no ORM.
"""
import pathlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

OPS_DIR = pathlib.Path(__file__).parent
DB_PATH = OPS_DIR / "outreach.db"

# Runbook's "Follow-Up Timing" section: days to add to move from one cadence
# step to the next. Step 12 has no next step — it's closed out manually.
CADENCE_STEPS = [1, 2, 4, 7, 12]
CADENCE_GAP_DAYS = {1: 1, 2: 2, 4: 3, 7: 5}  # gap FROM this step TO the next one

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical TEXT NOT NULL DEFAULT '',
    priority_rank INTEGER,
    score INTEGER,
    company_name TEXT NOT NULL,
    city_metro TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    review_signal TEXT NOT NULL DEFAULT '',
    size_signal TEXT NOT NULL DEFAULT '',
    primary_service TEXT NOT NULL DEFAULT '',
    lead_leakage TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    personalization_hook TEXT NOT NULL DEFAULT '',
    demo_scenario TEXT NOT NULL DEFAULT '',
    demo_questions TEXT NOT NULL DEFAULT '[]',
    decision_maker_name TEXT NOT NULL DEFAULT '',
    decision_maker_role TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email_or_contact_url TEXT NOT NULL DEFAULT '',
    linkedin TEXT NOT NULL DEFAULT '',
    facebook TEXT NOT NULL DEFAULT '',
    instagram TEXT NOT NULL DEFAULT '',
    preferred_channel TEXT NOT NULL DEFAULT '',
    outreach_angle TEXT NOT NULL DEFAULT '',
    slug_suggestion TEXT NOT NULL DEFAULT '',
    assigned_rep TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    source_urls TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Lead',
    cadence_step INTEGER NOT NULL DEFAULT 1,
    last_touch_at TEXT,
    next_touch_at TEXT,
    client_id TEXT,
    demo_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS touches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    cadence_step_at_time INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS script_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    cadence_step INTEGER NOT NULL,
    channel TEXT NOT NULL,
    title TEXT NOT NULL,
    body_template TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL,
    booking_link TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

# First-run default team — freely renamed/added-to afterward via
# PATCH/POST /api/outreach/reps. Rename cascades into prospects.assigned_rep
# so existing assignments follow the new name instead of orphaning.
DEFAULT_REPS = ["Larry", "VA1", "VA2"]

# Seeded verbatim from the "Leadguard Outbound - How to Run the Play" runbook.
# Merge fields: {{company}}, {{name}}, {{vertical}}, {{hook}}, {{demo_link}},
# {{decision_maker_role}}. Editable afterward via PATCH /api/outreach/scripts/{key}.
DEFAULT_SCRIPTS = [
    {
        "key": "call_owner",
        "cadence_step": 1,
        "channel": "phone",
        "title": "Call — Owner / decision-maker",
        "body_template": (
            "Hi {{name}}, it's {{rep}}. Quick reason for the call — I built an AI demo "
            "specifically for {{company}}, your site, and the {{vertical}} industry, and while "
            "I was on it I noticed something: {{hook}} That's not just a missed call, it's a "
            "missed job. Three minutes to try it, no pitch deck. It's built to support your "
            "team, not replace them — it catches the conversations you're currently losing, "
            "handles the repetitive questions, and hands off a clean, complete lead instead of "
            "a voicemail. Nothing to buy today — mind if I text or email you the link?"
        ),
    },
    {
        "key": "call_gatekeeper",
        "cadence_step": 1,
        "channel": "phone",
        "title": "Call — Receptionist / gatekeeper",
        "body_template": (
            "Hi, hoping you can point me the right way — this is {{rep}}. I put together a demo "
            "built specifically for {{company}}'s site and the {{vertical}} industry, not a "
            "generic tool, that shows how it could support whoever's handling calls and intake "
            "right now. Not about replacing anyone — more like a 24/7 backup that answers the "
            "basics and hands off a cleaner lead. Who's the best person to send that to?"
        ),
    },
    {
        "key": "voicemail",
        "cadence_step": 1,
        "channel": "voicemail",
        "title": "Voicemail",
        "body_template": (
            "Hey {{name}}, it's {{rep}}. Built an AI demo specifically for {{company}} and the "
            "{{vertical}} industry — not a generic pitch. Shows how the leads you're missing "
            "after-hours get answered and handed off clean. I'll text and email the link. If "
            "it's useful, I'd love 15 minutes to walk you through it."
        ),
    },
    {
        "key": "text_after_voicemail",
        "cadence_step": 1,
        "channel": "text",
        "title": "Text — after voicemail",
        "body_template": (
            "Hey {{name}} - {{rep}} here. I just left a quick message. Here is the demo I built "
            "for {{company}}: {{demo_link}}. Try the three questions I listed in the email. It "
            "was created from public website information and is not affiliated with your team "
            "unless you approve it."
        ),
    },
    {
        "key": "email",
        "cadence_step": 2,
        "channel": "email",
        "title": "Email",
        "body_template": (
            "Subject: A working demo for {{company}} (not a pitch)\n\n"
            "{{hook}}\n\n"
            "I built a working AI demo specifically for {{company}}, your site, and the "
            "{{vertical}} industry — not a deck, not a mockup: {{demo_link}}\n\n"
            "Three real questions worth trying:\n{{demo_questions}}\n\n"
            "Quick disclosure: built from publicly available info on {{company}}'s site. Not "
            "live on your site, and we're not affiliated unless you say so.\n\n"
            "If it catches your attention, 15 minutes is all I need to show you what's "
            "happening behind it."
        ),
    },
    {
        "key": "video_outline",
        "cadence_step": 4,
        "channel": "video",
        "title": "60-90 second video — outline",
        "body_template": (
            "1. Start on {{company}}'s website and point to the exact leak: {{hook}}\n"
            "2. Say clearly that the assistant supports the current team; it does not replace "
            "them.\n"
            "3. Open the unique demo URL: {{demo_link}}\n"
            "4. Ask one realistic customer/client question.\n"
            "5. Show the assistant asking smart follow-ups.\n"
            "6. Show the lead intelligence: service/case type, urgency, revenue/case signal, "
            "recommended routing.\n"
            "7. Close with: \"If this gets your attention, give me 15 minutes and I'll show how "
            "it would support your current team on the real site.\""
        ),
    },
    {
        "key": "day7_followup",
        "cadence_step": 7,
        "channel": "phone",
        "title": "Day 7 — follow-up",
        "body_template": (
            "Did you get a chance to try the {{company}} demo? I only need 3 minutes of your "
            "reaction. Here's the link again in case it got buried: {{demo_link}}"
        ),
    },
    {
        "key": "day12_closeloop",
        "cadence_step": 12,
        "channel": "phone",
        "title": "Day 12 — close the loop",
        "body_template": (
            "Closing the loop on the demo I sent for {{company}} — happy to disable it if it's "
            "not useful. If you're not the right person for website/customer intake decisions, "
            "who would be?"
        ),
    },
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def next_cadence_step(step: int) -> Optional[int]:
    idx = CADENCE_STEPS.index(step)
    return CADENCE_STEPS[idx + 1] if idx + 1 < len(CADENCE_STEPS) else None


def compute_next_touch(from_step: int, from_time: datetime) -> Optional[str]:
    gap = CADENCE_GAP_DAYS.get(from_step)
    return (from_time + timedelta(days=gap)).isoformat() if gap else None


STAGES = ["Lead", "Prospect", "Demo Performed", "Client Agreement", "Closed"]
RATINGS = ["", "not_interested", "interested", "hot"]

# Old 7-status board (Not Started/Working/Follow-up Due/Engaged/Won/Lost/Paused)
# replaced by the 5-stage sales pipeline above (2026-08-14) — every prospect starts
# life as a Lead and is manually promoted from there, per Larry's call. Existing rows
# get remapped once here rather than left on the old vocabulary the UI no longer
# offers. "Lost" has no stage equivalent by design — it's tracked as a flag so a
# card keeps whatever stage it reached instead of losing that history.
_STATUS_REMAP = {
    "Not Started": "Lead",
    "Working": "Lead",
    "Follow-up Due": "Lead",
    "Paused": "Lead",
    "Engaged": "Prospect",
    "Won": "Closed",
}


def init_db():
    with db_session() as conn:
        conn.executescript(SCHEMA)
        for migration in [
            "ALTER TABLE prospects ADD COLUMN rating TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE prospects ADD COLUMN product TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE prospects ADD COLUMN mrr_value REAL",
            "ALTER TABLE prospects ADD COLUMN setup_amount REAL",
            "ALTER TABLE prospects ADD COLUMN lost INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE prospects ADD COLUMN lost_reason TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE prospects ADD COLUMN has_video INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE reps ADD COLUMN booking_link TEXT NOT NULL DEFAULT ''",
        ]:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.execute(
            "UPDATE prospects SET lost = 1, lost_reason = 'Marked lost before pipeline redesign', "
            "status = 'Lead' WHERE status = 'Lost'"
        )
        for old, new in _STATUS_REMAP.items():
            conn.execute("UPDATE prospects SET status = ? WHERE status = ?", (new, old))
        existing_keys = {r["key"] for r in conn.execute("SELECT key FROM script_templates").fetchall()}
        for s in DEFAULT_SCRIPTS:
            if s["key"] in existing_keys:
                continue
            conn.execute(
                """INSERT INTO script_templates (key, cadence_step, channel, title, body_template, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (s["key"], s["cadence_step"], s["channel"], s["title"], s["body_template"], _now()),
            )
        rep_count = conn.execute("SELECT COUNT(*) AS n FROM reps").fetchone()["n"]
        if rep_count == 0:
            for i, name in enumerate(DEFAULT_REPS):
                conn.execute(
                    "INSERT INTO reps (name, position, created_at) VALUES (?, ?, ?)",
                    (name, i, _now()),
                )


init_db()
