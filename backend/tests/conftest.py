import os
import tempfile

# Must run before any `app.*` module is imported anywhere in the test session, since
# app/config.py reads LEADGUARD_DATA_DIR at import time. conftest.py is always imported
# first by pytest, which is what makes this reliable.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="leadguard_test_")
os.environ["LEADGUARD_DATA_DIR"] = _TEST_DATA_DIR
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import pytest

from app.db import db_session, init_db


@pytest.fixture(autouse=True)
def clean_db():
    """Fresh, isolated state before every test — a real temp SQLite file, not mocked."""
    init_db()
    with db_session() as conn:
        for table in ("messages", "conversations", "leads", "chunks", "sources", "faqs", "business_facts"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            """UPDATE business SET name='Test Business', assistant_name='', flow_script='',
               scheduling_link='', handoff_webhook_url='', handoff_email='',
               monthly_message_limit=500"""
        )
    yield
