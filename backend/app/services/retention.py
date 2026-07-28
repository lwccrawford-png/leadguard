from datetime import datetime, timedelta, timezone

from ..db import db_session

CONVERSATION_RETENTION_DAYS = 90


def purge_old_conversations(days: int = CONVERSATION_RETENTION_DAYS) -> int:
    """Delete conversation transcripts older than `days`. Messages cascade with them.
    Leads survive (conversation_id is set NULL) since they're the durable business record —
    only the raw chat transcript, which may carry visitor PII, is time-limited."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db_session() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,))
        return cur.rowcount
