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
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    name TEXT,
    email TEXT,
    phone TEXT,
    intent TEXT NOT NULL DEFAULT 'general_inquiry',
    notes TEXT,
    good_to_know TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    claimed_by TEXT,
    outcome TEXT,
    handoff_notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
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
        ]:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
        row = conn.execute("SELECT id FROM business WHERE id = 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO business (id) VALUES (1)")
