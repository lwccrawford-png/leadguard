import html
import os

import requests

from .handoff import INTENT_LABELS

RESEND_API_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT = 5


def notify(to_email: str, business_name: str, lead: dict) -> bool:
    """Send a real-time lead-notification email via Resend, straight to the client's
    own handoff_email — the zero-setup default alongside handoff.notify()'s webhook
    path, not a replacement for it (see docs/BIA_native_notifications.md). No-ops if
    Resend isn't configured or the client hasn't set a notification email."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL")
    if not api_key or not from_email or not to_email:
        return False

    intent = lead.get("intent") or "general_inquiry"
    label = INTENT_LABELS.get(intent, intent)

    contact_bits = [x for x in [lead.get("name"), lead.get("email"), lead.get("phone")] if x]
    contact_line = html.escape(" / ".join(contact_bits)) if contact_bits else "No contact info given"

    body = f"<p><strong>{html.escape(label)}</strong> — {html.escape(business_name)}</p><p>{contact_line}</p>"
    if lead.get("notes"):
        body += f"<p><strong>Notes:</strong> {html.escape(lead['notes'])}</p>"
    body += '<p style="color:#888;font-size:12px;">Sent automatically the moment this lead was captured.</p>'

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": f"[{business_name}] New lead — {label}",
        "html": body,
    }
    try:
        resp = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=REQUEST_TIMEOUT,
        )
        return resp.ok
    except requests.RequestException:
        return False
