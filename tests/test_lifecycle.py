"""Tests for the lifecycle state machine (EFF-02).

No database required — the lifecycle guard is pure Python.
"""

import pytest

from brm.lifecycle import (
    ALLOWED_TRANSITIONS,
    ALL_STATUSES,
    HEALTH_STATUSES,
    IllegalTransitionError,
    STATUS_DETECTED,
    STATUS_IN_REVIEW,
    STATUS_PROCESSED,
    STATUS_REJECTED,
    STATUS_SUMMARY_FAILED,
    STATUS_VERIFIED,
    assert_transition,
)


# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------


def test_detected_to_processed_allowed():
    """detected → processed is a valid transition (AI summary success)."""
    assert_transition(STATUS_DETECTED, STATUS_PROCESSED)


def test_detected_to_summary_failed_allowed():
    """detected → summary_failed is a valid transition (AI summary failure)."""
    assert_transition(STATUS_DETECTED, STATUS_SUMMARY_FAILED)


def test_summary_failed_to_processed_allowed():
    """summary_failed → processed is allowed (retry succeeded)."""
    assert_transition(STATUS_SUMMARY_FAILED, STATUS_PROCESSED)


def test_processed_to_in_review_allowed():
    """processed → in_review is allowed (surfaced to reviewer)."""
    assert_transition(STATUS_PROCESSED, STATUS_IN_REVIEW)


def test_in_review_to_verified_allowed():
    """in_review → verified is allowed (reviewer approved)."""
    assert_transition(STATUS_IN_REVIEW, STATUS_VERIFIED)


def test_in_review_to_rejected_allowed():
    """in_review → rejected is allowed (reviewer marked as noise)."""
    assert_transition(STATUS_IN_REVIEW, STATUS_REJECTED)


def test_in_review_self_loop_allowed():
    """in_review → in_review is allowed (reviewer re-edits summary; finding #11)."""
    assert_transition(STATUS_IN_REVIEW, STATUS_IN_REVIEW)


# ---------------------------------------------------------------------------
# Forbidden transitions
# ---------------------------------------------------------------------------


def test_detected_to_verified_raises():
    """detected → verified must be rejected (skips summary and review steps)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_DETECTED, STATUS_VERIFIED)


def test_verified_to_detected_raises():
    """verified → detected must be rejected (terminal state)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_VERIFIED, STATUS_DETECTED)


def test_verified_to_rejected_raises():
    """verified → rejected must be rejected (terminal state)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_VERIFIED, STATUS_REJECTED)


def test_rejected_to_detected_raises():
    """rejected → detected must be rejected (terminal state)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_REJECTED, STATUS_DETECTED)


def test_detected_to_in_review_raises():
    """detected → in_review must be rejected (must go through summary first)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_DETECTED, STATUS_IN_REVIEW)


def test_processed_to_detected_raises():
    """processed → detected must be rejected (no backward transitions)."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_PROCESSED, STATUS_DETECTED)


def test_in_review_to_summary_failed_raises():
    """in_review → summary_failed must be rejected."""
    with pytest.raises(IllegalTransitionError):
        assert_transition(STATUS_IN_REVIEW, STATUS_SUMMARY_FAILED)


# ---------------------------------------------------------------------------
# No Phase 5/6 states
# ---------------------------------------------------------------------------


def test_no_phase_56_states():
    """Phase 5/6 taxonomy states must NOT appear in lifecycle.py."""
    forbidden = {"classified", "pending_effective", "active", "superseded"}
    assert not forbidden.intersection(set(ALL_STATUSES)), (
        f"Phase 5/6 states found in ALL_STATUSES: {forbidden.intersection(set(ALL_STATUSES))}"
    )


def test_summary_failed_in_all_statuses():
    """summary_failed must be in ALL_STATUSES (operational safety state)."""
    assert STATUS_SUMMARY_FAILED in ALL_STATUSES


# ---------------------------------------------------------------------------
# Health statuses
# ---------------------------------------------------------------------------


def test_health_statuses_typed():
    """HEALTH_STATUSES contains exactly the three typed values."""
    assert HEALTH_STATUSES == {"unknown", "healthy", "failed"}


def test_health_statuses_no_free_form():
    """HEALTH_STATUSES does not contain arbitrary strings."""
    assert "broken" not in HEALTH_STATUSES
    assert "ok" not in HEALTH_STATUSES
    assert "error" not in HEALTH_STATUSES


# ---------------------------------------------------------------------------
# ALLOWED_TRANSITIONS structure
# ---------------------------------------------------------------------------


def test_all_statuses_have_transitions_entry():
    """Every status in ALL_STATUSES has an entry in ALLOWED_TRANSITIONS."""
    for status in ALL_STATUSES:
        assert status in ALLOWED_TRANSITIONS, (
            f"Status '{status}' missing from ALLOWED_TRANSITIONS"
        )


def test_terminal_states_have_empty_transitions():
    """verified and rejected are terminal — no outgoing transitions."""
    assert ALLOWED_TRANSITIONS[STATUS_VERIFIED] == set()
    assert ALLOWED_TRANSITIONS[STATUS_REJECTED] == set()
