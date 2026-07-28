import requests

WEBHOOK_TIMEOUT = 5

INTENT_LABELS = {
    "event_rsvp": "🎟️ EVENT RSVP",
    "meetup_request": "☕ MEETUP REQUEST",
    "call_booking": "📅 CALL BOOKING",
    "human_request": "🙋 WANTS A HUMAN",
    "unresolved_question": "❓ BOT COULDN'T ANSWER",
    "complaint": "⚠️ COMPLAINT",
    "leadership_inquiry": "⭐ LEADERSHIP/PARTNER INQUIRY",
    "general_inquiry": "💬 GENERAL INQUIRY",
    "urgent_crisis": "🚨 URGENT — CRISIS",
}


def notify(webhook_url: str, business_name: str, lead: dict, notify_email: str = "") -> bool:
    """POST a lead to the configured handoff webhook. Slack-compatible envelope (top-level
    "text") so a Slack Incoming Webhook URL works directly. Also includes flat "notify_email"
    and "subject" fields so a Zapier/Make/n8n scenario can map an Email action's To/Subject
    straight from the payload — the recipient is whatever the business has set in LeadGuard's
    own dashboard, not hardcoded inside the automation."""
    if not webhook_url:
        return False

    intent = lead.get("intent") or "general_inquiry"
    label = INTENT_LABELS.get(intent, intent)

    summary_bits = [f"*{lead.get('name') or 'A visitor'}*"]
    if lead.get("email"):
        summary_bits.append(lead["email"])
    if lead.get("phone"):
        summary_bits.append(lead["phone"])
    text = f"{label} — {business_name}: " + " / ".join(summary_bits)
    if lead.get("notes"):
        text += f"\nNotes: {lead['notes']}"

    payload = {
        "text": text,
        "subject": f"[{business_name}] New lead — {label}",
        "notify_email": notify_email,
        "business": business_name,
        "lead": lead,
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=WEBHOOK_TIMEOUT)
        return resp.ok
    except requests.RequestException:
        return False
