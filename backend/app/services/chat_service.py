from __future__ import annotations

import json
from datetime import datetime, timezone

import anthropic

from ..config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from ..db import db_session
from . import handoff, retrieval

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDS = 4

TOOLS = [
    {
        "name": "capture_lead",
        "description": "Save a visitor's contact info as a lead and alert the business. Call this "
        "whenever the visitor gives you a name/email/phone, wants a follow-up, wants to book/schedule "
        "something (share the scheduling link in your reply too, if one is configured), wants to RSVP or "
        "attend an event (solo or bringing others), wants to meet up in person (e.g. grab lunch/coffee), "
        "explicitly asks for a real person, expresses a complaint or bad experience, or asks about "
        "volunteering/leading/hosting/partnering. Call it as soon as you have enough info to be useful to a "
        "human follow-up — don't wait until the very end of the conversation.\n\n"
        "MANDATORY, no exceptions: the moment you fail to answer the same or a similar question twice, or "
        "the knowledge base has nothing relevant after a couple of tries, call capture_lead immediately "
        "with intent=unresolved_question — right then, in that same turn, even if name/email/phone are all "
        "still empty. Do not wait for contact info first. Leave name/email/phone blank if you don't have "
        "them yet; put what the visitor was asking in notes. A missed handoff here is worse than a sparse "
        "lead record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "intent": {
                    "type": "string",
                    "enum": [
                        "event_rsvp",
                        "meetup_request",
                        "call_booking",
                        "human_request",
                        "unresolved_question",
                        "complaint",
                        "leadership_inquiry",
                        "general_inquiry",
                        "urgent_crisis",
                    ],
                    "description": "What kind of follow-up this is, so the team can triage/divide it up.",
                },
                "notes": {
                    "type": "string",
                    "description": "What they want, plus any specifics mentioned: which event, how many "
                    "guests/friends coming, preferred timing, location, what question you couldn't answer, "
                    "what they're complaining about, or anything else the team needs to act on this without "
                    "re-asking the visitor.",
                },
            },
            "required": [],
        },
    },
]


def _get_business():
    with db_session() as conn:
        row = conn.execute("SELECT * FROM business WHERE id = 1").fetchone()
    return dict(row) if row else {}


def _get_or_create_conversation(session_id: str, visitor_ip):
    with db_session() as conn:
        row = conn.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO conversations (session_id, created_at, visitor_ip) VALUES (?, ?, ?)",
            (session_id, datetime.now(timezone.utc).isoformat(), visitor_ip),
        )
        return cur.lastrowid


def _save_message(conversation_id: int, role: str, content: str):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, datetime.now(timezone.utc).isoformat()),
        )


def _load_history(conversation_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, MAX_HISTORY_MESSAGES),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _system_prompt(business: dict, context_chunks: list) -> str:
    context_text = "\n\n".join(f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks) or "No matching knowledge base content found for this question."
    today = datetime.now().strftime("%A, %Y-%m-%d")

    parts = [f'You are the AI assistant for "{business.get("name") or "this business"}". Today is {today}.']

    parts.append(
        "SAFETY (always applies, takes priority over everything else): If a visitor's message signals "
        "real crisis — suicidal ideation, self-harm, abuse, or a safety emergency — do not try to counsel "
        "or resolve it yourself. Respond with care, tell them to contact 988 (Suicide & Crisis Lifeline, "
        "US) or call 911 / local emergency services if they're in immediate danger, and call capture_lead "
        "with notes flagging it as urgent so a real person follows up. If a visitor asks for medical, "
        "legal, or mental-health advice beyond what's in the knowledge base, don't improvise an answer — "
        "say that's outside what you can advise on and point them to a qualified professional."
    )

    script = (business.get("flow_script") or "").strip()
    if script:
        parts.append("Follow these instructions for how to behave, written by the business owner:\n" + script)
    else:
        parts.append("Be friendly, professional, and helpful. Qualify what the visitor needs and capture their contact info if they're interested.")

    if business.get("scheduling_link"):
        parts.append(f"When it's time to book/schedule, share this link: {business['scheduling_link']}")

    parts.append(
        "Answer using the KNOWLEDGE BASE below when relevant. If you don't know, say so and offer to "
        "have the business follow up. Call capture_lead whenever you get the visitor's contact info or "
        "they want a follow-up/booking. Keep replies short and conversational. This is a plain-text chat "
        "bubble, not a document — never use markdown formatting (no **bold**, no ## headers, no bullet "
        "lists with *) — write in plain sentences, using line breaks only for natural pauses."
    )

    parts.append(
        "EXAMPLE of the unresolved_question rule (follow this pattern exactly):\n"
        "Visitor: \"What's your refund policy?\"\n"
        "You: [reply that you don't have that, offer to have the team follow up] "
        "[in the SAME turn, call capture_lead with intent=unresolved_question, name/email/phone left blank, "
        "notes=\"Asked about refund policy, not in knowledge base\"]\n"
        "You do NOT wait for a second attempt, and you do NOT wait for contact info first — the tool call "
        "happens in the same turn as your very first \"I don't know\" on a knowledge-base gap that sounds "
        "important to the visitor (pricing, policies, guarantees). Asking the visitor for their email is a "
        "separate, following step, not a precondition for calling the tool."
    )

    parts.append("KNOWLEDGE BASE:\n" + context_text)
    return "\n\n".join(parts)


def _execute_tool(tool_name: str, tool_input: dict, business: dict, conversation_id: int) -> dict:
    if tool_name == "capture_lead":
        intent = tool_input.get("intent") or "general_inquiry"
        notified = handoff.notify(business.get("handoff_webhook_url", ""), business.get("name", "your business"), {**tool_input, "intent": intent})
        with db_session() as conn:
            conn.execute(
                "INSERT INTO leads (conversation_id, name, email, phone, intent, notes, handoff_notified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    tool_input.get("name"),
                    tool_input.get("email"),
                    tool_input.get("phone"),
                    intent,
                    tool_input.get("notes", ""),
                    1 if notified else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return {"saved": True, "business_notified": notified}

    return {"error": f"Unknown tool {tool_name}"}


def handle_message(session_id: str, user_message: str, visitor_ip: str | None = None) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"reply": "The assistant isn't configured yet — the site owner needs to set ANTHROPIC_API_KEY in the backend .env file."}

    business = _get_business()
    conversation_id = _get_or_create_conversation(session_id, visitor_ip)
    _save_message(conversation_id, "user", user_message)

    context_chunks = retrieval.retrieve(user_message, top_k=5)
    system_prompt = _system_prompt(business, context_chunks)
    messages = _load_history(conversation_id)
    collected_text = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError:
            fallback = "Sorry, I'm having a connection issue right now — please try again in a moment."
            _save_message(conversation_id, "assistant", fallback)
            return {"reply": fallback}

        # Claude can emit text AND call a tool in the same turn (e.g. explain + capture_lead) —
        # collect text from every round, not just the final one, or it gets silently dropped.
        collected_text.extend(block.text for block in response.content if block.type == "text" and block.text)

        if response.stop_reason != "tool_use":
            final_text = "\n\n".join(collected_text).strip()
            _save_message(conversation_id, "assistant", final_text)
            return {"reply": final_text}

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = _execute_tool(block.name, block.input, business, conversation_id)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    fallback = "Sorry, I'm having trouble completing that right now — could you leave your contact info and we'll follow up?"
    _save_message(conversation_id, "assistant", fallback)
    return {"reply": fallback}
