from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import anthropic

from ..config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from ..db import db_session
from . import faq_matching, handoff, rate_limit, retrieval

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDS = 4

BASE_TOOLS = [
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
                "discovery_phase": {
                    "type": "string",
                    "enum": [
                        "fact_finding",
                        "price_shopping",
                        "comparing_providers",
                        "evaluating_fit",
                        "ready_to_book",
                    ],
                    "description": "Where the visitor was in their buying journey when you captured them — "
                    "see the DISCOVERY PHASES section of your instructions for what each one means.",
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

SCHEDULING_LINK_TOOL = {
    "name": "get_scheduling_link",
    "description": "Get the booking link for this business, pre-filled with whatever contact info the "
    "visitor has already given you (name/email/phone) so they don't have to retype it on the scheduling "
    "page. Call this whenever you're ready to send the visitor to book — do not paste or retype the "
    "scheduling link yourself, always call this tool so it can be filled in correctly. Share the returned "
    "url in your reply exactly as given; the chat widget turns it into a clickable link automatically.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
        },
        "required": [],
    },
}


def _build_tools(business: dict) -> list:
    if business.get("scheduling_link"):
        return BASE_TOOLS + [SCHEDULING_LINK_TOOL]
    return BASE_TOOLS


def _build_prefilled_link(base_url: str, name: str = "", email: str = "", phone: str = "") -> str:
    parts = urlparse(base_url)
    params = dict(parse_qsl(parts.query))

    if name:
        params.setdefault("name", name)
        first, _, last = name.partition(" ")
        params.setdefault("firstName", first)
        if last:
            params.setdefault("lastName", last)
    if email:
        params.setdefault("email", email)
    if phone:
        params.setdefault("phone", phone)

    new_query = urlencode(params)
    return urlunparse(parts._replace(query=new_query))


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


def _save_message(conversation_id: int, role: str, content: str, latency_ms: int = None, input_tokens: int = None, output_tokens: int = None):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at, latency_ms, input_tokens, output_tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (conversation_id, role, content, datetime.now(timezone.utc).isoformat(), latency_ms, input_tokens, output_tokens),
        )


def _get_facts():
    with db_session() as conn:
        rows = conn.execute("SELECT label, value FROM business_facts ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def _load_history(conversation_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, MAX_HISTORY_MESSAGES),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _system_prompt(business: dict, context_chunks: list, matched_faq: dict = None, facts: list = None) -> str:
    today = datetime.now().strftime("%A, %Y-%m-%d")

    business_name = business.get("name") or "this business"
    assistant_name = (business.get("assistant_name") or "").strip()
    if assistant_name:
        parts = [f'Your name is {assistant_name}. You are the AI assistant for "{business_name}". Today is {today}.']
        parts.append(f'If you state a name for yourself anywhere — a greeting, when asked who you are, anywhere — it must be {assistant_name}. Never invent, use, or default to any other name for yourself under any circumstances. You don\'t need to lead with your name in every message, but if you say one, it is always {assistant_name}.')
    else:
        parts = [f'You are the AI assistant for "{business_name}". Today is {today}.']

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
        parts.append(
            "When it's time to book/schedule, call the get_scheduling_link tool (passing along any "
            "name/email/phone you already have) and share the url it returns — don't type or remember the "
            "link yourself. Pre-filling it saves the visitor from retyping their info on the booking page."
        )

    parts.append(
        "DISCOVERY PHASES — silently classify which phase the visitor is in from their messages, and let "
        "it shape your response and recommendation:\n"
        "- fact_finding: basic informational questions (hours, services, general \"what do you do\"). "
        "Just answer directly. Don't push a next step yet, but a soft, low-pressure invitation to go "
        "deeper is fine if it fits naturally.\n"
        "- price_shopping: asking about cost specifically. Give whatever range/context is in your "
        "knowledge, then recommend a discovery call for an accurate quote for their situation.\n"
        "- comparing_providers: weighing this business against alternatives. Lead with genuine "
        "differentiators from your knowledge, then recommend a discovery call so they can ask direct "
        "questions.\n"
        "- evaluating_fit: trying to determine if this business solves THEIR specific situation (more "
        "personal than fact_finding). Ask one or two clarifying questions, give preliminary guidance, "
        "then recommend a discovery call.\n"
        "- ready_to_book: they've signaled they want to move forward. Skip the soft-sell — go straight "
        "to booking, capturing their info, or offering a direct call/text.\n"
        "\n"
        "Regardless of phase: every substantive conversation must work toward one of exactly four "
        "closing actions — (1) booking/scheduling, (2) capturing contact info for follow-up, (3) a "
        "clickable phone call, or (4) a clickable text message. Never let a real conversation just trail "
        "off with information and no next step. Whenever you call capture_lead, include the "
        "discovery_phase you identified."
    )

    parts.append(
        "NEVER ASSUME THE VISITOR'S SPECIFIC GOAL. Your knowledge base may lean heavily toward one "
        "particular use case just because that's what the business's own marketing emphasizes most "
        "(e.g., a credit repair business's site might talk a lot about qualifying for a mortgage, even "
        "though plenty of visitors want credit repair for entirely different reasons — a car loan, a "
        "job application, or just general peace of mind). That emphasis in your knowledge base is not "
        "evidence about what THIS visitor wants. If they haven't told you their specific goal, ask — "
        "in neutral, open terms — rather than presuming one. Don't phrase your own question in a way "
        "that presumes an answer either (avoid leading with \"are you looking to buy a home?\" as your "
        "first guess; ask \"what are you hoping to accomplish?\" instead).\n"
        "EXAMPLE — visitor: \"Hi, my name is Lawrence and my credit score is 509.\" You should "
        "acknowledge the score, briefly explain generally how you help, and ask what's driving this "
        "for them — not respond as if you already know they're trying to qualify for a mortgage."
    )

    parts.append(
        "Answer using the KNOWLEDGE BASE below when relevant. If you don't know, say so and offer to "
        "have the business follow up. Call capture_lead whenever you get the visitor's contact info or "
        "they want a follow-up/booking. Keep replies short and conversational. This is a plain-text chat "
        "bubble, not a document — never use markdown formatting (no **bold**, no ## headers, no bullet "
        "lists with *) — write in plain sentences, using line breaks only for natural pauses."
    )

    parts.append(
        "EXAMPLE of the unresolved_question rule (follow this pattern exactly — this example topic is "
        "illustrative only, apply the PATTERN to whatever topic is actually missing, and note that an "
        "APPROVED FAQ MATCH or BUSINESS FACTS entry below always overrides this — if the topic IS covered "
        "there, answer from it directly and do not treat it as unresolved):\n"
        "Visitor: \"Do you have a location in Alaska?\"\n"
        "You: [reply that you don't have that, offer to have the team follow up] "
        "[in the SAME turn, call capture_lead with intent=unresolved_question, name/email/phone left blank, "
        "notes=\"Asked about an Alaska location, not in knowledge base\"]\n"
        "You do NOT wait for a second attempt, and you do NOT wait for contact info first — the tool call "
        "happens in the same turn as your very first \"I don't know\" on a knowledge-base gap that sounds "
        "important to the visitor (pricing, policies, guarantees). Asking the visitor for their email is a "
        "separate, following step, not a precondition for calling the tool."
    )

    if facts:
        facts_text = "\n".join(f"- {f['label']}: {f['value']}" for f in facts)
        parts.append(
            "BUSINESS FACTS (structured, always trust these over anything else for these specific "
            "items):\n" + facts_text
        )

    if matched_faq:
        parts.append(
            "APPROVED FAQ MATCH — this question was matched to a pre-approved FAQ with high confidence. "
            "Answer from this directly (you may rephrase naturally to fit the conversation, but do not "
            "contradict it, and do not treat this as uncertain or in need of further research):\n"
            f"Q: {matched_faq['question']}\nA: {matched_faq['answer']}"
        )
    else:
        context_text = (
            "\n\n".join(f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks)
            or "No matching knowledge base content found for this question."
        )
        parts.append("KNOWLEDGE BASE:\n" + context_text)

    return "\n\n".join(parts)


def _execute_tool(tool_name: str, tool_input: dict, business: dict, conversation_id: int) -> dict:
    if tool_name == "capture_lead":
        intent = tool_input.get("intent") or "general_inquiry"
        notified = handoff.notify(
            business.get("handoff_webhook_url", ""),
            business.get("name", "your business"),
            {**tool_input, "intent": intent},
            notify_email=business.get("handoff_email", ""),
        )
        with db_session() as conn:
            conn.execute(
                "INSERT INTO leads (conversation_id, name, email, phone, intent, discovery_phase, notes, handoff_notified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    tool_input.get("name"),
                    tool_input.get("email"),
                    tool_input.get("phone"),
                    intent,
                    tool_input.get("discovery_phase"),
                    tool_input.get("notes", ""),
                    1 if notified else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return {"saved": True, "business_notified": notified}

    if tool_name == "get_scheduling_link":
        base_url = business.get("scheduling_link") or ""
        if not base_url:
            return {"error": "No scheduling link configured for this business."}
        url = _build_prefilled_link(
            base_url,
            name=tool_input.get("name", ""),
            email=tool_input.get("email", ""),
            phone=tool_input.get("phone", ""),
        )
        return {"url": url}

    return {"error": f"Unknown tool {tool_name}"}


def handle_message(session_id: str, user_message: str, visitor_ip: str | None = None) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"reply": "The assistant isn't configured yet — the site owner needs to set ANTHROPIC_API_KEY in the backend .env file."}

    if not rate_limit.check_burst_limit(session_id):
        return {"reply": "You're sending messages a little fast — please wait a moment and try again."}

    business = _get_business()

    within_limit, used, limit = rate_limit.check_monthly_limit(business)
    if not within_limit:
        conversation_id = _get_or_create_conversation(session_id, visitor_ip)
        _save_message(conversation_id, "user", user_message)
        fallback = "Thanks for reaching out! We're at capacity for automated replies right now, but the team will follow up with you directly."
        _save_message(conversation_id, "assistant", fallback)

        with db_session() as conn:
            already_notified_this_month = conn.execute(
                "SELECT 1 FROM leads WHERE intent = 'capacity_reached' AND created_at >= ?",
                (datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(),),
            ).fetchone()

        notes = f"Monthly message cap reached ({used}/{limit}). Visitor's message: {user_message[:300]}"
        notified = False
        if not already_notified_this_month:
            # Only alert once per month — every message after the cap would otherwise spam the
            # webhook/email for every visitor who talks to an already-capped assistant.
            notified = handoff.notify(
                business.get("handoff_webhook_url", ""),
                business.get("name", "your business"),
                {"intent": "capacity_reached", "notes": notes},
                notify_email=business.get("handoff_email", ""),
            )

        with db_session() as conn:
            conn.execute(
                "INSERT INTO leads (conversation_id, intent, notes, status, handoff_notified, created_at) VALUES (?, 'capacity_reached', ?, 'new', ?, ?)",
                (conversation_id, notes, 1 if notified else 0, datetime.now(timezone.utc).isoformat()),
            )
        return {"reply": fallback}

    conversation_id = _get_or_create_conversation(session_id, visitor_ip)
    _save_message(conversation_id, "user", user_message)

    # Source-priority routing (V1_UPDATE_SPEC.md §2A/§4.3): check the approved FAQ fast path
    # first. A confident match skips general knowledge-base retrieval entirely — smaller
    # prompt, fewer tokens, and an answer grounded in pre-approved text rather than a chunk dump.
    matched_faq = faq_matching.match(user_message)
    context_chunks = [] if matched_faq else retrieval.retrieve(user_message, top_k=5)
    facts = _get_facts()
    system_prompt = _system_prompt(business, context_chunks, matched_faq=matched_faq, facts=facts)
    tools = _build_tools(business)
    messages = _load_history(conversation_id)
    collected_text = []
    total_input_tokens = 0
    total_output_tokens = 0
    start_time = time.perf_counter()

    def elapsed_ms():
        return int((time.perf_counter() - start_time) * 1000)

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError:
            fallback = "Sorry, I'm having a connection issue right now — please try again in a moment."
            _save_message(conversation_id, "assistant", fallback, elapsed_ms(), total_input_tokens, total_output_tokens)
            return {"reply": fallback}

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Claude can emit text AND call a tool in the same turn (e.g. explain + capture_lead) —
        # collect text from every round, not just the final one, or it gets silently dropped.
        collected_text.extend(block.text for block in response.content if block.type == "text" and block.text)

        if response.stop_reason != "tool_use":
            final_text = "\n\n".join(collected_text).strip()
            _save_message(conversation_id, "assistant", final_text, elapsed_ms(), total_input_tokens, total_output_tokens)
            return {"reply": final_text}

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = _execute_tool(block.name, block.input, business, conversation_id)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    fallback = "Sorry, I'm having trouble completing that right now — could you leave your contact info and we'll follow up?"
    _save_message(conversation_id, "assistant", fallback, elapsed_ms(), total_input_tokens, total_output_tokens)
    return {"reply": fallback}
