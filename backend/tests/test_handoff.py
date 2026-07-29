from unittest.mock import patch, MagicMock

from app.services import handoff


def test_notify_returns_false_with_no_webhook_url():
    assert handoff.notify("", "Acme Co", {"name": "Jane"}) is False


def test_notify_posts_slack_compatible_payload():
    with patch("app.services.handoff.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        result = handoff.notify(
            "https://hooks.example.com/webhook",
            "Acme Co",
            {"intent": "call_booking", "name": "Jane", "email": "jane@example.com", "notes": "wants a call"},
            notify_email="team@acme.com",
        )
    assert result is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert "text" in payload  # Slack Incoming Webhook reads this field directly
    assert "Jane" in payload["text"]
    assert payload["notify_email"] == "team@acme.com"
    assert payload["lead"]["email"] == "jane@example.com"


def test_notify_handles_unreachable_webhook_gracefully():
    with patch("app.services.handoff.requests.post", side_effect=Exception("connection refused")):
        # requests.exceptions.RequestException is what's actually caught; a generic Exception
        # here would propagate, which is intentional — we only swallow network-layer failures.
        pass
    with patch("app.services.handoff.requests.post") as mock_post:
        import requests

        mock_post.side_effect = requests.RequestException("connection refused")
        result = handoff.notify("https://unreachable.example.com", "Acme Co", {"name": "Jane"})
    assert result is False


def test_intent_label_used_in_summary_text():
    with patch("app.services.handoff.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        handoff.notify("https://hooks.example.com/webhook", "Acme Co", {"intent": "urgent_crisis", "notes": "flagged"})
    payload = mock_post.call_args.kwargs["json"]
    assert "URGENT" in payload["text"]
