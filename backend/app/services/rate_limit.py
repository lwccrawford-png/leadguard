import threading
import time
from datetime import datetime, timezone

from ..db import db_session

# Burst limiter: caps rapid-fire messages from a single widget session, independent of the
# monthly cap. In-memory only — fine for a single-instance deployment (which is what each
# client currently gets); would need a shared store (e.g. Redis) if a client's instance ever
# runs multiple worker processes.
BURST_WINDOW_SECONDS = 60
BURST_MAX_MESSAGES = 8

_burst_lock = threading.Lock()
_burst_log = {}  # session_id -> list[timestamp]


def check_burst_limit(session_id: str) -> bool:
    """Returns True if this session is within its burst allowance (and records the hit)."""
    now = time.time()
    with _burst_lock:
        hits = [t for t in _burst_log.get(session_id, []) if now - t < BURST_WINDOW_SECONDS]
        if len(hits) >= BURST_MAX_MESSAGES:
            _burst_log[session_id] = hits
            return False
        hits.append(now)
        _burst_log[session_id] = hits
        return True


def month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def messages_used_this_month() -> int:
    with db_session() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE role = 'user' AND created_at >= ?",
            (month_start_iso(),),
        ).fetchone()
    return row["c"]


def check_monthly_limit(business: dict) -> tuple[bool, int, int]:
    """Returns (within_limit, used, limit). limit <= 0 means unlimited."""
    limit = business.get("monthly_message_limit") or 0
    if limit <= 0:
        return True, 0, 0
    used = messages_used_this_month()
    return used < limit, used, limit
