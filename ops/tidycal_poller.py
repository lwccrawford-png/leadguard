#!/usr/bin/env python3
"""Poll the EvolveIQ TidyCal team for new and soon-due bookings, email an
alert for each. Meant to run on a short interval (systemd timer) — see
docs/VA_ONBOARDING_PLAYBOOK.md for the operating context this feeds.

Two separate things this watches for, since they need different handling:
  - A booking that's new since the last run -> immediate alert.
  - A booking starting in roughly 20-28h that hasn't been flagged yet ->
    "confirm this tomorrow" alert (the day-before confirmation call in the
    playbook). The 20-28h window (not exactly 24h) exists so a poll running
    every 10 minutes doesn't need to land on the exact hour to catch it.

Alerts go to TIDYCAL_ALERT_EMAIL — Larry today, since there's no VA yet.
Swapping that env var to a VA's address is the entire "plug and play" step
once one's hired; nothing else here changes.

State (which bookings have already been alerted on) lives in a small local
JSON file next to this script, not in the app's own database — this is
op-level bookkeeping, not product data.
"""
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

TIDYCAL_API_TOKEN = os.environ.get("TIDYCAL_API_TOKEN", "")
TIDYCAL_TEAM_ID = 11877  # EvolveIQ team — see docs/VA_ONBOARDING_PLAYBOOK.md
ALERT_EMAIL = os.environ.get("TIDYCAL_ALERT_EMAIL", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "")
RESEND_API_URL = "https://api.resend.com/emails"

STATE_PATH = pathlib.Path(__file__).parent / "tidycal_poller_state.json"
CONFIRM_WINDOW_MIN_HOURS = 20
CONFIRM_WINDOW_MAX_HOURS = 28


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"seen_booking_ids": [], "confirm_flagged_ids": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state))


def fetch_bookings() -> list:
    req = urllib.request.Request(
        f"https://tidycal.com/api/teams/{TIDYCAL_TEAM_ID}/bookings?per_page=100",
        headers={
            "Authorization": f"Bearer {TIDYCAL_API_TOKEN}",
            "Accept": "application/json",
            # urllib's default User-Agent ("Python-urllib/3.x") gets a 403 from
            # TidyCal's API even with a valid token — same request works fine
            # with curl's UA. Not a real browser claim, just avoiding the
            # generic-scraper fingerprint that's actually getting blocked.
            "User-Agent": "curl/8.7.1",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["data"]


def send_alert(subject: str, html: str) -> None:
    if not (ALERT_EMAIL and RESEND_API_KEY and RESEND_FROM_EMAIL):
        print(f"[tidycal_poller] no alert email configured, skipping: {subject}")
        return
    payload = json.dumps(
        {"from": RESEND_FROM_EMAIL, "to": [ALERT_EMAIL], "subject": subject, "html": html}
    ).encode()
    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except urllib.error.URLError as e:
        print(f"[tidycal_poller] failed to send alert ({subject!r}): {e}")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main() -> None:
    if not TIDYCAL_API_TOKEN:
        print("[tidycal_poller] TIDYCAL_API_TOKEN not set, nothing to do")
        return

    state = load_state()
    seen = set(state["seen_booking_ids"])
    confirm_flagged = set(state["confirm_flagged_ids"])

    bookings = [b for b in fetch_bookings() if not b.get("cancelled_at")]
    now = datetime.now(timezone.utc)

    new_bookings = [b for b in bookings if b["id"] not in seen]
    for b in new_bookings:
        contact = b.get("contact") or {}
        send_alert(
            f"New EvolveIQ demo booked — {contact.get('name', 'unknown')}",
            f"<p>{contact.get('name', 'unknown')} ({contact.get('email', 'no email')}) "
            f"booked a demo for {b['starts_at']}.</p>"
            f"<p><a href=\"https://tidycal.com/bookings/{b['slug']}\">View in TidyCal</a></p>",
        )
        seen.add(b["id"])

    due_soon = [
        b
        for b in bookings
        if b["id"] not in confirm_flagged
        and timedelta(hours=CONFIRM_WINDOW_MIN_HOURS)
        <= (_parse(b["starts_at"]) - now)
        <= timedelta(hours=CONFIRM_WINDOW_MAX_HOURS)
    ]
    if due_soon:
        items = "".join(
            f"<li>{(b.get('contact') or {}).get('name', '?')} — {b['starts_at']} "
            f"(<a href=\"https://tidycal.com/bookings/{b['slug']}\">details</a>)</li>"
            for b in due_soon
        )
        send_alert(
            f"{len(due_soon)} EvolveIQ call(s) to confirm tomorrow",
            f"<p>Run the call_confirmation script on each of these:</p><ul>{items}</ul>",
        )
        confirm_flagged.update(b["id"] for b in due_soon)

    save_state({"seen_booking_ids": list(seen), "confirm_flagged_ids": list(confirm_flagged)})


if __name__ == "__main__":
    main()
