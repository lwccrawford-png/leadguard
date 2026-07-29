from types import SimpleNamespace
from unittest.mock import patch

import anthropic

from app.db import db_session
from app.services import chat_service


def _text_response(text, input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _tool_use_response(tool_name, tool_input, tool_id="tool_1", text=None, input_tokens=100, output_tokens=20):
    content = []
    if text:
        content.append(SimpleNamespace(type="text", text=text))
    content.append(SimpleNamespace(type="tool_use", id=tool_id, name=tool_name, input=tool_input))
    return SimpleNamespace(
        stop_reason="tool_use",
        content=content,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


# ---------------------------------------------------------------- source-priority routing
# (V1_UPDATE_SPEC.md §2A/§4.3/§8, §7.2 "unnecessary research prevention")

def test_system_prompt_faq_match_skips_general_knowledge_base():
    matched_faq = {"question": "What is your refund policy?", "answer": "No refunds after 7 days.", "score": 0.9}
    context_chunks = [{"source": "https://example.com/page", "text": "unrelated page content"}]
    prompt = chat_service._system_prompt({"name": "Acme"}, context_chunks, matched_faq=matched_faq, facts=[])
    assert "APPROVED FAQ MATCH" in prompt
    assert "No refunds after 7 days." in prompt
    assert "KNOWLEDGE BASE:" not in prompt  # the general chunk dump must not appear alongside a FAQ hit


def test_system_prompt_no_match_falls_back_to_general_knowledge_base():
    context_chunks = [{"source": "https://example.com/page", "text": "our hours are 9 to 5"}]
    prompt = chat_service._system_prompt({"name": "Acme"}, context_chunks, matched_faq=None, facts=[])
    assert "KNOWLEDGE BASE:" in prompt
    assert "our hours are 9 to 5" in prompt
    # The phrase "APPROVED FAQ MATCH" legitimately appears once, as a cross-reference inside the
    # general few-shot instructions — but the actual dynamic section (with its trailing em-dash
    # header) must not be rendered when there's no real match.
    assert "APPROVED FAQ MATCH — this question was matched" not in prompt


def test_system_prompt_includes_facts_block_regardless_of_faq_match():
    facts = [{"label": "Phone", "value": "555-1234"}]
    prompt = chat_service._system_prompt({"name": "Acme"}, [], matched_faq=None, facts=facts)
    assert "BUSINESS FACTS" in prompt
    assert "555-1234" in prompt


def test_handle_message_skips_retrieval_on_faq_match(monkeypatch):
    """Full-path check: a confident FAQ match must prevent the general retrieval call
    entirely, not just omit it from the prompt — this is the actual token/latency saving."""
    fake_faq = {"question": "What are your hours?", "answer": "9-5 Monday to Friday.", "score": 0.9}
    monkeypatch.setattr(chat_service.faq_matching, "match", lambda q: fake_faq)

    retrieval_called = {"count": 0}

    def _spy_retrieve(*args, **kwargs):
        retrieval_called["count"] += 1
        return []

    monkeypatch.setattr(chat_service.retrieval, "retrieve", _spy_retrieve)

    with patch.object(chat_service.client.messages, "create", return_value=_text_response("We're open 9-5!")):
        result = chat_service.handle_message("session-faq-fastpath", "what are your hours")

    assert retrieval_called["count"] == 0
    assert "9-5" in result["reply"]


# ---------------------------------------------------------------- client-context retention

def test_load_history_returns_messages_in_chronological_order():
    conv_id = chat_service._get_or_create_conversation("session-history", None)
    chat_service._save_message(conv_id, "user", "first message")
    chat_service._save_message(conv_id, "assistant", "first reply")
    chat_service._save_message(conv_id, "user", "second message")

    history = chat_service._load_history(conv_id)

    assert [h["content"] for h in history] == ["first message", "first reply", "second message"]
    assert [h["role"] for h in history] == ["user", "assistant", "user"]


def test_get_or_create_conversation_reuses_same_session():
    conv_id_1 = chat_service._get_or_create_conversation("same-session", None)
    conv_id_2 = chat_service._get_or_create_conversation("same-session", None)
    assert conv_id_1 == conv_id_2


# ---------------------------------------------------------------- callback / human handoff

def test_capture_lead_tool_persists_and_notifies(monkeypatch):
    notified_calls = []
    monkeypatch.setattr(
        chat_service.handoff, "notify",
        lambda webhook, name, lead, notify_email="": notified_calls.append(lead) or True,
    )

    with patch.object(
        chat_service.client.messages, "create",
        side_effect=[
            _tool_use_response(
                "capture_lead",
                {"name": "Jane", "email": "jane@example.com", "intent": "call_booking", "notes": "wants a callback"},
                text="Sure, I'll have someone call you.",
            ),
            _text_response("Got it, Jane — someone will call you back soon."),
        ],
    ):
        result = chat_service.handle_message("session-callback", "can someone call me back?")

    assert "Jane" in result["reply"] or "call" in result["reply"].lower()
    assert len(notified_calls) == 1
    assert notified_calls[0]["email"] == "jane@example.com"

    with db_session() as conn:
        row = conn.execute("SELECT * FROM leads WHERE email = 'jane@example.com'").fetchone()
    assert row is not None
    assert row["intent"] == "call_booking"
    assert row["handoff_notified"] == 1


# ---------------------------------------------------------------- tool-failure handling

def test_handle_message_api_error_returns_graceful_fallback():
    with patch.object(chat_service.client.messages, "create", side_effect=anthropic.APIError("boom", request=None, body=None)):
        result = chat_service.handle_message("session-api-error", "hello")

    assert "connection issue" in result["reply"].lower()

    conv_id = chat_service._get_or_create_conversation("session-api-error", None)
    with db_session() as conn:
        row = conn.execute(
            "SELECT content, latency_ms FROM messages WHERE conversation_id = ? AND role = 'assistant'", (conv_id,)
        ).fetchone()
    assert row is not None
    assert "connection issue" in row["content"].lower()
    assert row["latency_ms"] is not None  # even a failed call should record how long we waited


# ---------------------------------------------------------------- monthly cap / capacity handling

def test_monthly_cap_blocks_before_calling_claude(monkeypatch):
    with db_session() as conn:
        conn.execute("UPDATE business SET monthly_message_limit = 1")

    call_count = {"n": 0}

    def _spy_create(*args, **kwargs):
        call_count["n"] += 1
        return _text_response("should not be reached")

    with patch.object(chat_service.client.messages, "create", side_effect=_spy_create):
        # First message consumes the only slot in the cap.
        chat_service.handle_message("session-cap-1", "hello")
        # Second message (any session) should now be over the cap and short-circuit before Claude.
        result = chat_service.handle_message("session-cap-2", "hello again")

    assert "capacity" in result["reply"].lower()
    assert call_count["n"] == 1  # only the first message actually reached the Claude client

    with db_session() as conn:
        row = conn.execute("SELECT * FROM leads WHERE intent = 'capacity_reached'").fetchone()
    assert row is not None
