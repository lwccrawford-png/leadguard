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
    last_crawled_at TEXT
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
        ]:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
        row = conn.execute("SELECT id FROM business WHERE id = 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO business (id) VALUES (1)")
