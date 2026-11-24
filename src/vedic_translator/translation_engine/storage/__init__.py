"""Storage subsystem: SQLite repositories, schema migrations, and state machine."""

from vedic_translator.translation_engine.storage.models import (
    JobStatus,
    TranslationJobRecord,
    TranslationUnitRecord,
    TranslationVersionRecord,
    UnitStatus,
    VersionStage,
    compute_source_content_hash,
)
from vedic_translator.translation_engine.storage.repository import TranslationStorage
from vedic_translator.translation_engine.storage.schema import (
    CURRENT_SCHEMA_VERSION,
    initialize_database,
)
from vedic_translator.translation_engine.storage.state_machine import (
    VALID_JOB_TRANSITIONS,
    VALID_UNIT_TRANSITIONS,
    is_valid_job_transition,
    is_valid_unit_transition,
    validate_job_transition,
    validate_unit_transition,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "JobStatus",
    "TranslationJobRecord",
    "TranslationStorage",
    "TranslationUnitRecord",
    "TranslationVersionRecord",
    "UnitStatus",
    "VALID_JOB_TRANSITIONS",
    "VALID_UNIT_TRANSITIONS",
    "VersionStage",
    "compute_source_content_hash",
    "initialize_database",
    "is_valid_job_transition",
    "is_valid_unit_transition",
    "validate_job_transition",
    "validate_unit_transition",
]
