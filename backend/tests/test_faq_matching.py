from datetime import datetime, timezone

from app.db import db_session
from app.services import faq_matching


def _add_faq(question, answer, category="", priority=0):
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO faqs (question, answer, category, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (question, answer, category, priority, now, now),
        )
    faq_matching.rebuild_index()


def test_no_faqs_returns_none():
    assert faq_matching.match("what are your hours") is None


def test_close_match_found():
    _add_faq("What is your refund policy?", "No refunds after 7 days.")
    result = faq_matching.match("what is your refund policy")
    assert result is not None
    assert result["answer"] == "No refunds after 7 days."


def test_plural_singular_variation_still_matches():
    # Regression test: plain TF-IDF treats "refund" and "refunds" as unrelated tokens
    # without stemming. text_matching.tokenize() strips common suffixes to fix this.
    _add_faq("What is your refund policy?", "No refunds after 7 days.")
    result = faq_matching.match("do you offer refunds")
    assert result is not None


def test_unrelated_question_does_not_match():
    _add_faq("What is your refund policy?", "No refunds after 7 days.")
    result = faq_matching.match("what services do you offer for teenagers")
    assert result is None


def test_best_match_wins_with_multiple_faqs():
    _add_faq("What are your hours?", "9-5 Monday to Friday.")
    _add_faq("What is your refund policy?", "No refunds after 7 days.")
    result = faq_matching.match("tell me about your refund policy")
    assert result["answer"] == "No refunds after 7 days."
