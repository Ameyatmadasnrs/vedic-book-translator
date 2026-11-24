"""Storage domain models and enums for translation jobs, units, and versions."""

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def compute_source_content_hash(
    original_text: str,
    transliteration: str | None = None,
    reference_english: str | None = None,
    commentary: str | None = None,
) -> str:
    """Compute deterministic SHA-256 hash of normalized source content.

    Uses ASCII Unit Separator (\x1f) to prevent cross-field boundary collision.
    """
    parts = [
        original_text.strip(),
        (transliteration or "").strip(),
        (reference_english or "").strip(),
        (commentary or "").strip(),
    ]
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JobStatus(StrEnum):
    """Lifecycle status of a translation job."""

    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class UnitStatus(StrEnum):
    """Lifecycle status of an individual translation unit."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    TRANSLATED = "TRANSLATED"
    QC_FAILED = "QC_FAILED"
    QC_PASSED = "QC_PASSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"


class VersionStage(StrEnum):
    """Source origin of a translation version."""

    AI_DRAFT = "AI_DRAFT"
    HUMAN_EDIT = "HUMAN_EDIT"
    RETRANSLATION = "RETRANSLATION"


class TranslationJobRecord(BaseModel):
    """Persistent database record for a book translation job."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    book_title: str
    source_language: str = "awa"
    target_language: str = "ru"
    provider_name: str
    model_name: str
    status: JobStatus = JobStatus.INITIALIZED
    total_units: int = 0
    completed_units: int = 0
    failed_units: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TranslationUnitRecord(BaseModel):
    """Persistent database record for a single translation unit linked to MVP A."""

    unit_id: str
    job_id: str
    canonical_id: str | None = None
    unit_type: str = "GENERIC_VERSE"
    sequence_order: int = 0
    chapter_index: int = 0
    section_index: int = 0
    content_hash: str
    source_original_text: str
    source_transliteration_text: str | None = None
    source_reference_english: str | None = None
    source_commentary: str | None = None
    status: UnitStatus = UnitStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TranslationVersionRecord(BaseModel):
    """Persistent versioned record of a translation draft or human correction."""

    version_id: str = Field(default_factory=lambda: str(uuid4()))
    unit_id: str
    version_number: int = 1
    source_stage: VersionStage = VersionStage.AI_DRAFT
    translated_verse_russian: str
    translated_commentary_russian: str | None = None
    translator_notes: str | None = None
    confidence_assessment: dict[str, Any] | None = None
    qc_results: dict[str, Any] | None = None
    token_usage: dict[str, Any] | None = None
    model_name: str | None = None
    editor_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
