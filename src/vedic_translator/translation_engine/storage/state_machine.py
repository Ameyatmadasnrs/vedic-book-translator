"""State machine transitions and invariant validation for translation jobs and units."""

from vedic_translator.core.exceptions import InvalidStateTransitionError
from vedic_translator.translation_engine.storage.models import JobStatus, UnitStatus

# Explicit valid state transition graph for high-level translation jobs
VALID_JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.INITIALIZED: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.PAUSED, JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.PAUSED: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),  # Terminal state
    JobStatus.FAILED: {JobStatus.RUNNING, JobStatus.INITIALIZED},  # Retryable
}

# Explicit valid state transition graph for individual translation units
# Modeled strictly after Plan Section 7 state diagram
VALID_UNIT_TRANSITIONS: dict[UnitStatus, set[UnitStatus]] = {
    # Unit waiting to be picked up by worker
    UnitStatus.PENDING: {
        UnitStatus.PROCESSING,
    },
    # Unit actively being translated by worker
    UnitStatus.PROCESSING: {
        UnitStatus.TRANSLATED,  # Model produced candidate translation
        UnitStatus.QC_FAILED,  # Network/API timeout or generation error
        UnitStatus.PENDING,  # Job interruption recovery or worker release
    },
    # Candidate translation produced, entering quality audit
    UnitStatus.TRANSLATED: {
        UnitStatus.QC_PASSED,  # All deterministic quality checks pass
        UnitStatus.QC_FAILED,  # Quality invariant broken
    },
    # Unit failed quality audit or experienced transient errors
    UnitStatus.QC_FAILED: {
        UnitStatus.PENDING,  # Re-queued for auto-retry
        UnitStatus.NEEDS_REVIEW,  # Max retries exceeded; routed to human editor
    },
    # Unit passed deterministic quality checks
    UnitStatus.QC_PASSED: {
        UnitStatus.APPROVED,  # Auto-approved (high confidence)
        UnitStatus.NEEDS_REVIEW,  # Flagged for human review (ambiguous or low confidence)
    },
    # Unit queued for human editorial gate
    UnitStatus.NEEDS_REVIEW: {
        UnitStatus.APPROVED,  # Human editor signs off or saves edits
        UnitStatus.PENDING,  # Human editor requests re-translation with new guidance
    },
    # Approved final translation
    UnitStatus.APPROVED: {
        UnitStatus.NEEDS_REVIEW,  # Human editor revokes or requests modification
    },
}


def is_valid_job_transition(current: JobStatus, target: JobStatus) -> bool:
    """Check if job state transition is permitted without raising an error."""
    if current == target:
        return True
    return target in VALID_JOB_TRANSITIONS.get(current, set())


def validate_job_transition(current: JobStatus, target: JobStatus) -> None:
    """Validate job state transition, raising InvalidStateTransitionError on violation."""
    if not is_valid_job_transition(current, target):
        valid_targets = sorted(s.value for s in VALID_JOB_TRANSITIONS.get(current, set()))
        raise InvalidStateTransitionError(
            f"Invalid job state transition: '{current.value}' -> '{target.value}'. "
            f"Allowed transitions from '{current.value}': {valid_targets or 'None (terminal)'}."
        )


def is_valid_unit_transition(current: UnitStatus, target: UnitStatus) -> bool:
    """Check if unit state transition is permitted without raising an error."""
    if current == target:
        return True
    return target in VALID_UNIT_TRANSITIONS.get(current, set())


def validate_unit_transition(current: UnitStatus, target: UnitStatus) -> None:
    """Validate unit state transition, raising InvalidStateTransitionError on violation."""
    if not is_valid_unit_transition(current, target):
        valid_targets = sorted(s.value for s in VALID_UNIT_TRANSITIONS.get(current, set()))
        raise InvalidStateTransitionError(
            f"Invalid unit state transition: '{current.value}' -> '{target.value}'. "
            f"Allowed transitions from '{current.value}': {valid_targets or 'None (terminal)'}."
        )
