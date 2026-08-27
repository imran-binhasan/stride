"""Unit tests for activity intensity calculation and idle handling."""

from src.services.time_service import calculate_activity_score


def test_activity_score_idle():
    # When user is idle, score is 0.0 regardless of inputs
    assert calculate_activity_score(keystrokes=10, mouse_px=200, is_idle=True) == 0.0


def test_activity_score_active():
    # Moderate activity
    score_mid = calculate_activity_score(keystrokes=20, mouse_px=400, is_idle=False)
    assert 40.0 <= score_mid <= 60.0

    # High activity (caps at 100%)
    score_high = calculate_activity_score(keystrokes=80, mouse_px=2000, is_idle=False)
    assert score_high == 100.0

    # Zero input but not flagged idle
    score_zero = calculate_activity_score(keystrokes=0, mouse_px=0, is_idle=False)
    assert score_zero == 0.0
