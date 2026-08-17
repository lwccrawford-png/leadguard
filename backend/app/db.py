import sqlite3
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS business (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL DEFAULT 'My Business',
    assistant_name TEXT NOT NULL DEFAULT '',
    assistant_image_url TEXT NOT NULL DEFAULT '',
    website_url TEXT NOT NULL DEFAULT '',
    scheduling_link TEXT NOT NULL DEFAULT '',
    handoff_webhook_url TEXT NOT NULL DEFAULT '',
    handoff_email TEXT NOT NULL DEFAULT '',
    flow_script TEXT NOT NULL DEFAULT '',
    accent_color TEXT NOT NULL DEFAULT '#4f46e5',
    monthly_message_limit INTEGER NOT NULL DEFAULT 500,
    rot_aging_minutes INTEGER NOT NULL DEFAULT 1440,
    rot_rotting_minutes INTEGER NOT NULL DEFAULT 4320,
    pipeline_enabled INTEGER NOT NULL DEFAULT 0,
    -- Gates the dashboard's "Configure intelligence & routing" link (priority scoring,
    -- conditional routing) — tier-derived, pushed from ops/launcher_server.py's
    -- TIER_FEATURES the same way pipeline_enabled is.
    priority_routing_enabled INTEGER NOT NULL DEFAULT 0,
    last_crawled_at TEXT,
    -- Free-text provenance for what seeded this client's knowledge base — e.g.
    -- "BIP: HVAC v1.0" or "Manual". Purely informational (nothing reads this to change
    -- chat behavior); exists so it's visible at a glance which clients came from a BIP
    -- versus hand-built, instead of BIP content being indistinguishable once pasted in.
    knowledge_source TEXT NOT NULL DEFAULT '',
    -- Custom initial greeting shown when the widget opens. Empty means "use the
    -- auto-generated preset" (built from assistant_name/name) — set here to override it.
    greeting TEXT NOT NULL DEFAULT '',
    -- Prospect demo fields (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md). Only meaningful for
    -- instances of type "demo" in ops/clients.json; unused/blank for real client instances.
    -- disclosure_text is required non-affiliation copy shown on the public /demo page.
    -- demo_suggested_questions is a JSON array of exactly 3 question strings.
    -- demo_expires_at (ISO-8601, nullable) and demo_enabled gate GET /demo directly —
    -- null demo_expires_at means "no expiration set" (never expires). demo_enabled is
    -- flipped to 0 by the launcher's Promote-to-client action, since a promoted client's
    -- public demo page (with its "not affiliated" banner) no longer describes them.
    disclosure_text TEXT NOT NULL DEFAULT '',
    demo_suggested_questions TEXT NOT NULL DEFAULT '[]',
    demo_expires_at TEXT,
    demo_enabled INTEGER NOT NULL DEFAULT 1,
    booking_link TEXT NOT NULL DEFAULT ''
);

-- A "source" is either a crawled site page (source_type='site', url set) or a manually
-- fed document (source_type='manual', label set). Both get chunked into `chunks` the same way.
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('site', 'manual')),
    url TEXT,
    label TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_label TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    visitor_ip TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER
);

-- Structured Layer 1 knowledge (V1_UPDATE_SPEC.md §2A): flexible key/value facts
-- (hours, phone, address, short policy summaries) — always cheap enough to include
-- in every system prompt directly, no retrieval call needed.
CREATE TABLE IF NOT EXISTS business_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    -- 'bip' if written by the Fast BIP Import tool, 'manual' for anything hand-typed
    -- in the dashboard or pulled in by the site crawl. Powers the knowledge-composition
    -- readout (what fraction of a client's knowledge base is LeadGuard's reusable
    -- vertical content vs. content specific to them) — doesn't affect chat behavior.
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Structured Layer 1 knowledge: approved FAQs (V1_UPDATE_SPEC.md §3.5). Matched via a
-- dedicated lightweight index before falling back to general knowledge-base retrieval.
CREATE TABLE IF NOT EXISTS faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    name TEXT,
    email TEXT,
    phone TEXT,
    intent TEXT NOT NULL DEFAULT 'general_inquiry',
    -- Where the visitor was in their buying journey when captured — a fixed, business-agnostic
    -- taxonomy standing in for the spec's generic 12-stage funnel model. Complementary to
    -- `intent` (what the follow-up is for), not a replacement for it.
    discovery_phase TEXT,
    notes TEXT,
    good_to_know TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    claimed_by TEXT,
    outcome TEXT,
    handoff_notified INTEGER NOT NULL DEFAULT 0,
    -- SMS marketing consent for call_booking-intent leads from the marketing site's demo
    -- request form — disclosed as "by submitting this form..." next to the phone field there,
    -- so providing a phone number IS the consent signal, not a separate checkbox. Kept as its
    -- own column (not folded into notes) so it's queryable evidence, not just typed text.
    -- Unset (0) for every other lead source/intent.
    sms_consent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Client -> agency support/change requests. Reachable at /support/ with no login,
-- since the managed-service client typically has no dashboard access at all. Notifies
-- the agency (not the client's own handoff_webhook_url/handoff_email, which route to
-- the client's team about their leads) via a separate, agency-level webhook/email set
-- once in the backend's own .env, shared across every deployed client instance.
CREATE TABLE IF NOT EXISTS support_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    details TEXT NOT NULL,
    urgency TEXT NOT NULL DEFAULT 'normal',
    contact_info TEXT,
    screenshot_data_uri TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Prospect demo engagement tracking (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md). No
-- prospect_demo_id column — each demo is its own isolated instance (see CLAUDE.md,
-- single-tenant-per-instance), so every row in this table already belongs to exactly
-- one prospect by construction. Only meaningful for instances of type "demo".
CREATE TABLE IF NOT EXISTS demo_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    session_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- Pipeline add-on (paid feature, gated by business.pipeline_enabled): a business-configurable
-- second board for tracking claimed leads through an ongoing sales/membership process, distinct
-- from the fixed New/Claimed/Done Leads funnel. Up to 8 stages, business-defined labels/order.
CREATE TABLE IF NOT EXISTS pipeline_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    position INTEGER NOT NULL,
    notes_enabled INTEGER NOT NULL DEFAULT 0,
    is_won INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Only meaningful for the single stage flagged is_won=1 — the product/service dropdown shown
-- on cards sitting in that stage.
CREATE TABLE IF NOT EXISTS pipeline_dropdown_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_id INTEGER NOT NULL REFERENCES pipeline_stages(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_id INTEGER NOT NULL REFERENCES pipeline_stages(id) ON DELETE CASCADE,
    name TEXT,
    email TEXT,
    phone TEXT,
    notes TEXT,
    outcome_notes TEXT,
    chosen_option_id INTEGER REFERENCES pipeline_dropdown_options(id) ON DELETE SET NULL,
    claimed_by TEXT,
    -- Set when this card was promoted from a claimed lead, per BIA_configurable_pipeline_board.md.
    source_lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


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


def init_db():
    with db_session() as conn:
        conn.executescript(SCHEMA)
        for migration in [
            "ALTER TABLE leads ADD COLUMN intent TEXT NOT NULL DEFAULT 'general_inquiry'",
            "ALTER TABLE leads ADD COLUMN status TEXT NOT NULL DEFAULT 'new'",
            "ALTER TABLE leads ADD COLUMN claimed_by TEXT",
            "ALTER TABLE leads ADD COLUMN good_to_know TEXT",
            "ALTER TABLE leads ADD COLUMN outcome TEXT",
            "ALTER TABLE business ADD COLUMN handoff_email TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN assistant_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN assistant_image_url TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN monthly_message_limit INTEGER NOT NULL DEFAULT 500",
            "ALTER TABLE messages ADD COLUMN latency_ms INTEGER",
            "ALTER TABLE messages ADD COLUMN input_tokens INTEGER",
            "ALTER TABLE messages ADD COLUMN output_tokens INTEGER",
            "ALTER TABLE leads ADD COLUMN discovery_phase TEXT",
            "ALTER TABLE business ADD COLUMN rot_aging_minutes INTEGER NOT NULL DEFAULT 1440",
            "ALTER TABLE business ADD COLUMN rot_rotting_minutes INTEGER NOT NULL DEFAULT 4320",
            "ALTER TABLE business ADD COLUMN pipeline_enabled INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE support_requests ADD COLUMN screenshot_data_uri TEXT",
            "ALTER TABLE support_requests ADD COLUMN status TEXT NOT NULL DEFAULT 'new'",
            "ALTER TABLE business ADD COLUMN knowledge_source TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN greeting TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business_facts ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'",
            "ALTER TABLE faqs ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'",
            "ALTER TABLE business ADD COLUMN disclosure_text TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN demo_suggested_questions TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE business ADD COLUMN demo_expires_at TEXT",
            "ALTER TABLE business ADD COLUMN demo_enabled INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE business ADD COLUMN industry TEXT NOT NULL DEFAULT ''",
            # Prospect-demo booking CTA (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md) — seeded
            # from the assigned rep's booking link at demo-generation time and pushed live
            # again whenever that rep's link changes, so it never goes stale between demos.
            "ALTER TABLE business ADD COLUMN booking_link TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE business ADD COLUMN priority_routing_enabled INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE leads ADD COLUMN sms_consent INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
        row = conn.execute("SELECT id FROM business WHERE id = 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO business (id) VALUES (1)")
