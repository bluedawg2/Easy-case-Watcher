"""Change lifecycle state machine — Phase 1 subset.

This module defines the six status constants reachable in Phase 1,
the typed health-status value set, the allowed-transition map, and the
transition guard function.

Phase 1 status values:
    detected        diff produced, Change row created
    processed       AI summary attached
    summary_failed  AI summary call failed — retryable, never silent (finding #3)
    in_review       surfaced in the review queue
    verified        reviewer approved
    rejected        reviewer marked as noise (not a real rule change)

Phase 5/6 values (NOT in this module):
    classified, pending_effective, active, superseded — do not add them here.

Health status values (Source.health_status — finding #20):
    unknown     initial state; source has not yet been fetched
    healthy     last fetch succeeded
    failed      last fetch failed (tri-state FETCH_FAILED outcome)
"""

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_DETECTED = "detected"
STATUS_PROCESSED = "processed"
STATUS_SUMMARY_FAILED = "summary_failed"
STATUS_IN_REVIEW = "in_review"
STATUS_VERIFIED = "verified"
STATUS_REJECTED = "rejected"

ALL_STATUSES: list[str] = [
    STATUS_DETECTED,
    STATUS_PROCESSED,
    STATUS_SUMMARY_FAILED,
    STATUS_IN_REVIEW,
    STATUS_VERIFIED,
    STATUS_REJECTED,
]

# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    # A diff was produced — the AI summary attempt comes next.
    STATUS_DETECTED: {STATUS_PROCESSED, STATUS_SUMMARY_FAILED},
    # The AI summary succeeded but failed on a retry; a re-attempt transitions to processed.
    STATUS_SUMMARY_FAILED: {STATUS_PROCESSED},
    # Summary is attached; surface in the review queue.
    STATUS_PROCESSED: {STATUS_IN_REVIEW},
    # Reviewer can approve, reject, or re-edit (self-loop) the summary.
    # The self-loop lets a reviewer correct a summary more than once (finding #11).
    STATUS_IN_REVIEW: {STATUS_VERIFIED, STATUS_REJECTED, STATUS_IN_REVIEW},
    # Terminal states — no outgoing transitions.
    STATUS_VERIFIED: set(),
    STATUS_REJECTED: set(),
}

# ---------------------------------------------------------------------------
# Health status constants (Source.health_status)
# ---------------------------------------------------------------------------

HEALTH_STATUSES: set[str] = {"unknown", "healthy", "failed"}

# ---------------------------------------------------------------------------
# Transition guard
# ---------------------------------------------------------------------------


class IllegalTransitionError(Exception):
    """Raised when an illegal lifecycle status transition is attempted."""


def assert_transition(current: str, target: str) -> None:
    """Raise IllegalTransitionError if current → target is not an allowed transition.

    Args:
        current: The current status of the Change record.
        target: The desired new status.

    Raises:
        IllegalTransitionError: If the transition is not in ALLOWED_TRANSITIONS.
        KeyError: If *current* is not a recognized status (programming error).
    """
    if target not in ALLOWED_TRANSITIONS[current]:
        raise IllegalTransitionError(
            f"Transition '{current}' → '{target}' is not allowed. "
            f"Allowed targets from '{current}': {ALLOWED_TRANSITIONS[current] or '{none}'}"
        )
