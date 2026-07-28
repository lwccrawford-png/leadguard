import requests

WEBHOOK_TIMEOUT = 5

INTENT_LABELS = {
    "event_rsvp": "🎟️ EVENT RSVP",
    "meetup_request": "☕ MEETUP REQUEST",
    "call_booking": "📅 CALL BOOKING",
    "general_inquiry": "💬 GENERAL INQUIRY",
    "urgent_crisis": "🚨 URGENT — CRISIS",
}


def notify(webhook_url: str, business_name: str, lead: dict) -> bool:
    """POST a lead to the configured handoff webhook. Slack-compatible envelope (top-level
    "text") so a Slack Incoming Webhook URL works directly; a Zapier/Make/n8n catch-webhook
    can read the full "lead" object to fan out to SMS, email, a CRM, etc."""
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

    payload = {"text": text, "business": business_name, "lead": lead}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=WEBHOOK_TIMEOUT)
        return resp.ok
    except requests.RequestException:
        return False
