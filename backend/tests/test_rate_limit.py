from app.services import rate_limit


def test_burst_limit_allows_up_to_max():
    session_id = "burst-test-session"
    for _ in range(rate_limit.BURST_MAX_MESSAGES):
        assert rate_limit.check_burst_limit(session_id) is True


def test_burst_limit_blocks_after_max():
    session_id = "burst-test-session-2"
    for _ in range(rate_limit.BURST_MAX_MESSAGES):
        rate_limit.check_burst_limit(session_id)
    assert rate_limit.check_burst_limit(session_id) is False


def test_burst_limit_is_per_session():
    for _ in range(rate_limit.BURST_MAX_MESSAGES):
        rate_limit.check_burst_limit("session-a")
    assert rate_limit.check_burst_limit("session-a") is False
    assert rate_limit.check_burst_limit("session-b") is True


def test_monthly_limit_unlimited_when_zero():
    within, used, limit = rate_limit.check_monthly_limit({"monthly_message_limit": 0})
    assert within is True
    assert limit == 0


def test_monthly_limit_within_when_under_cap():
    within, used, limit = rate_limit.check_monthly_limit({"monthly_message_limit": 500})
    assert within is True
    assert limit == 500
