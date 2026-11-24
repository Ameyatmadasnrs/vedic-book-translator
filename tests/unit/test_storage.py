"""Unit tests for SQLite storage layer, migrations, and job state machine."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from vedic_translator.core.exceptions import (
    InvalidStateTransitionError,
    RecordNotFoundError,
    StorageError,
)
from vedic_translator.translation_engine.storage import (
    JobStatus,
    TranslationJobRecord,
    TranslationStorage,
    TranslationUnitRecord,
    TranslationVersionRecord,
    UnitStatus,
    VersionStage,
    compute_source_content_hash,
    is_valid_job_transition,
    is_valid_unit_transition,
    validate_unit_transition,
)
from vedic_translator.translation_engine.storage.schema import (
    CURRENT_SCHEMA_VERSION,
    initialize_database,
)


@pytest.fixture
def storage(tmp_path: Path) -> TranslationStorage:
    """Fixture providing a file-backed TranslationStorage in temporary directory."""
    db_file = tmp_path / "test_workspace.db"
    return TranslationStorage(db_file)


@pytest.fixture
def sample_job(storage: TranslationStorage) -> TranslationJobRecord:
    """Fixture providing a registered translation job."""
    job = TranslationJobRecord(
        job_id=str(uuid4()),
        document_id=str(uuid4()),
        book_title="Sri Ramcharit Manas (Test)",
        source_language="awa",
        target_language="ru",
        provider_name="gemini",
        model_name="gemini-3.5-flash-lite",
        total_units=10,
        config={"temperature": 0.2},
    )
    return storage.create_job(job)


# -----------------------------------------------------------------------------
# 1. Schema & Migration Verification
# -----------------------------------------------------------------------------


def test_schema_initialization_wal_and_foreign_keys(tmp_path: Path) -> None:
    """Verify WAL mode, foreign keys, and migration tables are initialized."""
    db_file = tmp_path / "wal_test.db"
    storage = TranslationStorage(db_file)

    with storage.get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal"

        fk_on = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_on == 1

        migration_v1 = conn.execute(
            "SELECT version, description FROM schema_migrations WHERE version = 1;"
        ).fetchone()
        assert migration_v1 is not None
        assert migration_v1["version"] == 1
        assert "Initial schema" in migration_v1["description"]

        migration_v2 = conn.execute(
            "SELECT version, description FROM schema_migrations WHERE version = 2;"
        ).fetchone()
        assert migration_v2 is not None
        assert migration_v2["version"] == 2
        assert "idx_units_job_status_seq" in migration_v2["description"]

        # Verify composite index exists
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_units_job_status_seq';"
        ).fetchone()
        assert idx is not None
        assert idx["name"] == "idx_units_job_status_seq"


def test_foreign_key_enforcement(storage: TranslationStorage) -> None:
    """Verify inserting a unit with a non-existent job_id fails with foreign key violation."""
    unit = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id="non-existent-job-id",
        canonical_id="1.1",
        content_hash="dummy_hash",
        source_original_text="Test source text",
    )
    with pytest.raises(sqlite3.IntegrityError):
        # Direct insert to bypass repository or let upsert catch it
        with storage.get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO translation_units (
                        unit_id, job_id, canonical_id, unit_type, sequence_order,
                        chapter_index, section_index, content_hash, source_original_text,
                        status, attempts, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        unit.unit_id,
                        unit.job_id,
                        unit.canonical_id,
                        unit.unit_type,
                        unit.sequence_order,
                        unit.chapter_index,
                        unit.section_index,
                        unit.content_hash,
                        unit.source_original_text,
                        unit.status.value,
                        unit.attempts,
                        unit.created_at.isoformat(),
                        unit.updated_at.isoformat(),
                    ),
                )


# -----------------------------------------------------------------------------
# 2. Translation Jobs Lifecycle
# -----------------------------------------------------------------------------


def test_create_and_get_job(storage: TranslationStorage) -> None:
    """Verify job record persistence, retrieval, and fields."""
    job_id = str(uuid4())
    job = TranslationJobRecord(
        job_id=job_id,
        document_id="doc-123",
        book_title="Gita Press Ramcharit Manas",
        provider_name="gemini",
        model_name="gemini-3.5-flash-lite",
        status=JobStatus.INITIALIZED,
        config={"max_retries": 3},
    )
    created = storage.create_job(job)
    assert created.job_id == job_id

    retrieved = storage.get_job(job_id)
    assert retrieved is not None
    assert retrieved.book_title == "Gita Press Ramcharit Manas"
    assert retrieved.status == JobStatus.INITIALIZED
    assert retrieved.config == {"max_retries": 3}


def test_create_duplicate_job_raises_storage_error(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify creating a job with an existing job_id raises StorageError."""
    with pytest.raises(StorageError, match="already exists"):
        storage.create_job(sample_job)


def test_update_job_progress(storage: TranslationStorage, sample_job: TranslationJobRecord) -> None:
    """Verify atomic progress increments."""
    updated = storage.update_job_progress(
        sample_job.job_id, completed_increment=2, failed_increment=1, total_units=10
    )
    assert updated.total_units == 10
    assert updated.completed_units == 2
    assert updated.failed_units == 1

    updated2 = storage.update_job_progress(
        sample_job.job_id, completed_increment=3, failed_increment=0
    )
    assert updated2.completed_units == 5
    assert updated2.failed_units == 1


# -----------------------------------------------------------------------------
# 3. State Machine & Transitions
# -----------------------------------------------------------------------------


def test_job_state_machine_valid_transitions(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify standard happy-path job transitions: INITIALIZED -> RUNNING -> PAUSED -> RUNNING -> COMPLETED."""
    j1 = storage.update_job_status(sample_job.job_id, JobStatus.RUNNING)
    assert j1.status == JobStatus.RUNNING

    j2 = storage.update_job_status(sample_job.job_id, JobStatus.PAUSED)
    assert j2.status == JobStatus.PAUSED

    j3 = storage.update_job_status(sample_job.job_id, JobStatus.RUNNING)
    assert j3.status == JobStatus.RUNNING

    j4 = storage.update_job_status(sample_job.job_id, JobStatus.COMPLETED)
    assert j4.status == JobStatus.COMPLETED


def test_job_state_machine_invalid_transition(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify illegal job transition raises InvalidStateTransitionError."""
    # INITIALIZED -> COMPLETED directly is illegal
    assert not is_valid_job_transition(JobStatus.INITIALIZED, JobStatus.COMPLETED)
    with pytest.raises(InvalidStateTransitionError, match="Invalid job state transition"):
        storage.update_job_status(sample_job.job_id, JobStatus.COMPLETED)


def test_unit_state_machine_valid_transitions() -> None:
    """Verify unit state machine transitions against the approved plan."""
    # Happy path: PENDING -> PROCESSING -> TRANSLATED -> QC_PASSED -> APPROVED
    assert is_valid_unit_transition(UnitStatus.PENDING, UnitStatus.PROCESSING)
    assert is_valid_unit_transition(UnitStatus.PROCESSING, UnitStatus.TRANSLATED)
    assert is_valid_unit_transition(UnitStatus.TRANSLATED, UnitStatus.QC_PASSED)
    assert is_valid_unit_transition(UnitStatus.QC_PASSED, UnitStatus.APPROVED)

    # Failure & review branches
    assert is_valid_unit_transition(UnitStatus.PROCESSING, UnitStatus.QC_FAILED)
    assert is_valid_unit_transition(UnitStatus.TRANSLATED, UnitStatus.QC_FAILED)
    assert is_valid_unit_transition(UnitStatus.QC_FAILED, UnitStatus.PENDING)  # Retry
    assert is_valid_unit_transition(UnitStatus.QC_FAILED, UnitStatus.NEEDS_REVIEW)  # Max retries
    assert is_valid_unit_transition(UnitStatus.QC_PASSED, UnitStatus.NEEDS_REVIEW)  # Ambiguous
    assert is_valid_unit_transition(UnitStatus.NEEDS_REVIEW, UnitStatus.APPROVED)  # Human sign-off
    assert is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.NEEDS_REVIEW)  # Modification


def test_unit_state_machine_invalid_transitions() -> None:
    """Verify illegal unit state transitions raise InvalidStateTransitionError."""
    with pytest.raises(InvalidStateTransitionError):
        validate_unit_transition(UnitStatus.PENDING, UnitStatus.APPROVED)

    with pytest.raises(InvalidStateTransitionError):
        validate_unit_transition(UnitStatus.PENDING, UnitStatus.TRANSLATED)

    with pytest.raises(InvalidStateTransitionError):
        validate_unit_transition(UnitStatus.TRANSLATED, UnitStatus.APPROVED)


# -----------------------------------------------------------------------------
# 4. Units Persistence, Idempotency & Hash Changes
# -----------------------------------------------------------------------------


def test_unit_idempotent_upsert(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify upserting an identical unit does not reset an in-progress or translated status."""
    unit_id = str(uuid4())
    content_hash = compute_source_content_hash(
        original_text="कौसल्यादि नारि सब...", transliteration="kausalyādi nāri..."
    )

    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        canonical_id="1.188",
        unit_type="DOHA",
        sequence_order=1,
        content_hash=content_hash,
        source_original_text="कौसल्यादि नारि सब...",
        source_transliteration_text="kausalyādi nāri...",
    )
    storage.upsert_unit(unit)

    # Transition unit to PROCESSING then TRANSLATED
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING)
    storage.update_unit_status(unit_id, UnitStatus.TRANSLATED)

    current = storage.get_unit(unit_id)
    assert current is not None
    assert current.status == UnitStatus.TRANSLATED

    # Re-upserting the exact same unit must preserve TRANSLATED status (Idempotent!)
    storage.upsert_unit(unit)
    rechecked = storage.get_unit(unit_id)
    assert rechecked is not None
    assert rechecked.status == UnitStatus.TRANSLATED


def test_unit_source_hash_change_resets_to_pending(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify modifying source content detects hash change, resets attempts to 0 and status to PENDING."""
    unit_id = str(uuid4())
    hash_v1 = compute_source_content_hash(original_text="Text V1")

    unit_v1 = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        canonical_id="1.1",
        sequence_order=1,
        content_hash=hash_v1,
        source_original_text="Text V1",
    )
    storage.upsert_unit(unit_v1)
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING, increment_attempts=True)
    storage.update_unit_status(unit_id, UnitStatus.TRANSLATED)

    pre_check = storage.get_unit(unit_id)
    assert pre_check is not None
    assert pre_check.attempts == 1

    # Now simulate upstream correction to source text
    hash_v2 = compute_source_content_hash(original_text="Text V2 (Corrected)")
    unit_v2 = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        canonical_id="1.1",
        sequence_order=1,
        content_hash=hash_v2,
        source_original_text="Text V2 (Corrected)",
    )
    storage.upsert_unit(unit_v2)

    updated = storage.get_unit(unit_id)
    assert updated is not None
    assert updated.content_hash == hash_v2
    assert updated.source_original_text == "Text V2 (Corrected)"
    assert updated.status == UnitStatus.PENDING  # Reset to PENDING for re-translation!
    assert updated.attempts == 0  # Attempts reset to 0 for corrected source!


def test_batch_upsert_and_sequence_ordering(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify batch insertion of multiple units preserving strict reading order."""
    units = [
        TranslationUnitRecord(
            unit_id=str(uuid4()),
            job_id=sample_job.job_id,
            canonical_id=f"1.{i}",
            sequence_order=i,
            content_hash=compute_source_content_hash(f"Verse {i}"),
            source_original_text=f"Verse {i}",
        )
        for i in [3, 1, 2]  # Intentionally out of order
    ]
    count = storage.batch_upsert_units(units)
    assert count == 3

    fetched = storage.get_units_for_job(sample_job.job_id)
    assert len(fetched) == 3
    assert [u.sequence_order for u in fetched] == [1, 2, 3]


# -----------------------------------------------------------------------------
# 5. Interrupted Job Resumption & Recovery
# -----------------------------------------------------------------------------


def test_acquire_next_pending_unit(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify atomic worker acquisition of next sequential pending unit."""
    u1 = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id=sample_job.job_id,
        sequence_order=1,
        content_hash="h1",
        source_original_text="T1",
    )
    u2 = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id=sample_job.job_id,
        sequence_order=2,
        content_hash="h2",
        source_original_text="T2",
    )
    storage.batch_upsert_units([u1, u2])

    acquired1 = storage.acquire_next_pending_unit(sample_job.job_id)
    assert acquired1 is not None
    assert acquired1.unit_id == u1.unit_id
    assert acquired1.status == UnitStatus.PROCESSING
    assert acquired1.attempts == 1

    acquired2 = storage.acquire_next_pending_unit(sample_job.job_id)
    assert acquired2 is not None
    assert acquired2.unit_id == u2.unit_id
    assert acquired2.status == UnitStatus.PROCESSING
    assert acquired2.attempts == 1

    acquired3 = storage.acquire_next_pending_unit(sample_job.job_id)
    assert acquired3 is None  # No more PENDING units


def test_recover_interrupted_units_after_crash(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify recovering units stuck in PROCESSING back to PENDING without affecting completed units."""
    u1 = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id=sample_job.job_id,
        sequence_order=1,
        content_hash="h1",
        source_original_text="T1",
    )
    u2 = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id=sample_job.job_id,
        sequence_order=2,
        content_hash="h2",
        source_original_text="T2",
    )
    u3 = TranslationUnitRecord(
        unit_id=str(uuid4()),
        job_id=sample_job.job_id,
        sequence_order=3,
        content_hash="h3",
        source_original_text="T3",
    )
    storage.batch_upsert_units([u1, u2, u3])

    # Unit 1 is approved
    storage.update_unit_status(u1.unit_id, UnitStatus.PROCESSING)
    storage.update_unit_status(u1.unit_id, UnitStatus.TRANSLATED)
    storage.update_unit_status(u1.unit_id, UnitStatus.QC_PASSED)
    storage.update_unit_status(u1.unit_id, UnitStatus.APPROVED)

    # Unit 2 was in-flight (PROCESSING) when the process was killed
    storage.update_unit_status(u2.unit_id, UnitStatus.PROCESSING)

    # Unit 3 remains PENDING

    stats_before = storage.get_job_statistics(sample_job.job_id)
    assert stats_before["APPROVED"] == 1
    assert stats_before["PROCESSING"] == 1
    assert stats_before["PENDING"] == 1

    # Recover interrupted units
    recovered = storage.recover_interrupted_units(sample_job.job_id)
    assert recovered == 1

    stats_after = storage.get_job_statistics(sample_job.job_id)
    assert stats_after["APPROVED"] == 1
    assert stats_after["PROCESSING"] == 0
    assert stats_after["PENDING"] == 2

    # Verify unit 2 is now PENDING and has error note
    u2_recovered = storage.get_unit(u2.unit_id)
    assert u2_recovered is not None
    assert u2_recovered.status == UnitStatus.PENDING
    assert "Recovered from interrupted" in (u2_recovered.last_error or "")


# -----------------------------------------------------------------------------
# 6. Translation Versions & Audit Trail
# -----------------------------------------------------------------------------


def test_create_multiple_versions_and_audit_trail(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify multiple versions can be attached to one unit without overwriting earlier ones."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        sequence_order=1,
        content_hash="hash_doha",
        source_original_text="Doha original text",
    )
    storage.upsert_unit(unit)
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING)

    # Create Version 1 (AI draft) and transition unit to TRANSLATED
    v1 = TranslationVersionRecord(
        unit_id=unit_id,
        source_stage=VersionStage.AI_DRAFT,
        translated_verse_russian="Черновой перевод стиха (ИИ)",
        model_name="gemini-3.5-flash-lite",
        token_usage={"total_tokens": 50},
    )
    persisted_v1 = storage.create_version(unit_id, v1, new_unit_status=UnitStatus.TRANSLATED)
    assert persisted_v1.version_number == 1

    unit_check1 = storage.get_unit(unit_id)
    assert unit_check1 is not None
    assert unit_check1.status == UnitStatus.TRANSLATED

    # Move to QC_PASSED then NEEDS_REVIEW
    storage.update_unit_status(unit_id, UnitStatus.QC_PASSED)
    storage.update_unit_status(unit_id, UnitStatus.NEEDS_REVIEW)

    # Create Version 2 (Human editor correction) and transition to APPROVED
    v2 = TranslationVersionRecord(
        unit_id=unit_id,
        source_stage=VersionStage.HUMAN_EDIT,
        translated_verse_russian="Отредактированный стих редактором",
        editor_id="editor-alexey",
        translator_notes="Скорректирован падеж слова Бхагаван",
    )
    persisted_v2 = storage.create_version(unit_id, v2, new_unit_status=UnitStatus.APPROVED)
    assert persisted_v2.version_number == 2

    # Check that both versions exist and earlier one was NOT overwritten
    all_versions = storage.get_versions_for_unit(unit_id)
    assert len(all_versions) == 2
    assert all_versions[0].version_number == 1
    assert all_versions[0].translated_verse_russian == "Черновой перевод стиха (ИИ)"
    assert all_versions[0].source_stage == VersionStage.AI_DRAFT

    assert all_versions[1].version_number == 2
    assert all_versions[1].translated_verse_russian == "Отредактированный стих редактором"
    assert all_versions[1].source_stage == VersionStage.HUMAN_EDIT
    assert all_versions[1].editor_id == "editor-alexey"

    # Latest version retrieval
    latest = storage.get_latest_version(unit_id)
    assert latest is not None
    assert latest.version_number == 2

    # Unit status is now APPROVED
    unit_check2 = storage.get_unit(unit_id)
    assert unit_check2 is not None
    assert unit_check2.status == UnitStatus.APPROVED


def test_create_version_for_nonexistent_unit_raises_error(
    storage: TranslationStorage,
) -> None:
    """Verify creating a version for a missing unit raises RecordNotFoundError."""
    v = TranslationVersionRecord(
        unit_id="missing-unit-id",
        translated_verse_russian="Text",
    )
    with pytest.raises(RecordNotFoundError, match="does not exist"):
        storage.create_version("missing-unit-id", v)


def test_version_uniqueness_constraint(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify unique constraint on (unit_id, version_number)."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="h",
        source_original_text="T",
    )
    storage.upsert_unit(unit)

    with storage.get_connection() as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO translation_versions (
                    version_id, unit_id, version_number, source_stage,
                    translated_verse_russian, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (str(uuid4()), unit_id, 1, "AI_DRAFT", "V1", "2026-11-24T00:00:00"),
            )
            # Attempt duplicate (unit_id, 1)
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO translation_versions (
                        version_id, unit_id, version_number, source_stage,
                        translated_verse_russian, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        str(uuid4()),
                        unit_id,
                        1,
                        "AI_DRAFT",
                        "V1-dup",
                        "2026-11-24T00:00:00",
                    ),
                )


# -----------------------------------------------------------------------------
# 7. Targeted Audit Hardening & Invariant Verification Tests
# -----------------------------------------------------------------------------


def test_create_version_transaction_rollback_on_invalid_status_transition(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify atomicity: if new_unit_status validation fails, the version insert is rolled back."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="hash_rollback",
        source_original_text="Source for rollback test",
    )
    storage.upsert_unit(unit)
    unit_start = storage.get_unit(unit_id)
    assert unit_start is not None
    assert unit_start.status == UnitStatus.PENDING

    # Attempt to create version while illegally transitioning PENDING -> APPROVED directly
    v = TranslationVersionRecord(
        unit_id=unit_id,
        source_stage=VersionStage.AI_DRAFT,
        translated_verse_russian="Invalid transition draft",
    )
    with pytest.raises(InvalidStateTransitionError):
        storage.create_version(unit_id, v, new_unit_status=UnitStatus.APPROVED)

    # Invariant: unit status remains PENDING and no version was committed
    unit_after = storage.get_unit(unit_id)
    assert unit_after is not None
    assert unit_after.status == UnitStatus.PENDING

    versions = storage.get_versions_for_unit(unit_id)
    assert len(versions) == 0


def test_version_preservation_after_source_hash_change(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify old translation versions remain intact after source text is modified and unit resets."""
    unit_id = str(uuid4())
    hash_v1 = compute_source_content_hash("Original Text V1")
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash=hash_v1,
        source_original_text="Original Text V1",
    )
    storage.upsert_unit(unit)
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING)

    # Create Version 1
    v1 = TranslationVersionRecord(
        unit_id=unit_id,
        source_stage=VersionStage.AI_DRAFT,
        translated_verse_russian="Перевод версии 1",
    )
    storage.create_version(unit_id, v1, new_unit_status=UnitStatus.TRANSLATED)

    # Modify source text
    hash_v2 = compute_source_content_hash("Original Text V2 (Corrected)")
    unit_updated = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash=hash_v2,
        source_original_text="Original Text V2 (Corrected)",
    )
    storage.upsert_unit(unit_updated)

    # Unit is reset to PENDING and attempts reset to 0
    unit_check = storage.get_unit(unit_id)
    assert unit_check is not None
    assert unit_check.status == UnitStatus.PENDING
    assert unit_check.attempts == 0

    # Old version 1 is preserved in translation_versions
    versions = storage.get_versions_for_unit(unit_id)
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].translated_verse_russian == "Перевод версии 1"


def test_batch_upsert_resets_attempts_on_hash_change(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify batch_upsert_units resets attempts to 0 when source hash changes."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="h1",
        source_original_text="T1",
    )
    storage.batch_upsert_units([unit])
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING, increment_attempts=True)
    unit_p = storage.get_unit(unit_id)
    assert unit_p is not None
    assert unit_p.attempts == 1

    # Batch upsert with changed hash
    unit_v2 = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="h2",
        source_original_text="T2",
    )
    count = storage.batch_upsert_units([unit_v2])
    assert count == 1

    updated = storage.get_unit(unit_id)
    assert updated is not None
    assert updated.status == UnitStatus.PENDING
    assert updated.attempts == 0


def test_update_unit_status_error_preservation_and_clearing(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify error_message retention across review states and auto-clearing on success states."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="h",
        source_original_text="T",
    )
    storage.upsert_unit(unit)

    # 1. Failure sets error message
    storage.update_unit_status(unit_id, UnitStatus.PROCESSING)
    storage.update_unit_status(
        unit_id, UnitStatus.QC_FAILED, error_message="Glossary check failed: banned word 'бог'"
    )
    u1 = storage.get_unit(unit_id)
    assert u1 is not None
    assert u1.last_error == "Glossary check failed: banned word 'бог'"

    # 2. Transitioning to NEEDS_REVIEW with error_message=None PRESERVES the error
    storage.update_unit_status(unit_id, UnitStatus.NEEDS_REVIEW, error_message=None)
    u2 = storage.get_unit(unit_id)
    assert u2 is not None
    assert u2.last_error == "Glossary check failed: banned word 'бог'"

    # 3. Transitioning to APPROVED with error_message=None CLEARS the error
    storage.update_unit_status(unit_id, UnitStatus.APPROVED, error_message=None)
    u3 = storage.get_unit(unit_id)
    assert u3 is not None
    assert u3.last_error is None


def test_foreign_key_cascade_deletion(
    storage: TranslationStorage, sample_job: TranslationJobRecord
) -> None:
    """Verify ON DELETE CASCADE removes units and versions when a job is deleted."""
    unit_id = str(uuid4())
    unit = TranslationUnitRecord(
        unit_id=unit_id,
        job_id=sample_job.job_id,
        content_hash="h_cascade",
        source_original_text="Cascade test",
    )
    storage.upsert_unit(unit)

    v = TranslationVersionRecord(
        unit_id=unit_id,
        source_stage=VersionStage.AI_DRAFT,
        translated_verse_russian="Version cascade",
    )
    storage.create_version(unit_id, v)

    # Assert unit and version exist
    assert storage.get_unit(unit_id) is not None
    assert len(storage.get_versions_for_unit(unit_id)) == 1

    # Delete the parent job directly via SQL
    with storage.get_connection() as conn:
        with conn:
            conn.execute("DELETE FROM translation_jobs WHERE job_id = ?;", (sample_job.job_id,))

    # Invariant: unit and versions cascaded away
    assert storage.get_unit(unit_id) is None
    assert len(storage.get_versions_for_unit(unit_id)) == 0


def test_idempotent_database_initialization(tmp_path: Path) -> None:
    """Verify repeatedly calling initialize_database is safe, idempotent, and maintains schema version 2."""
    db_file = tmp_path / "idempotent_init.db"
    conn = sqlite3.connect(db_file)

    # First initialization
    initialize_database(conn)
    v1 = conn.execute("SELECT MAX(version) FROM schema_migrations;").fetchone()[0]
    assert v1 == CURRENT_SCHEMA_VERSION == 2

    # Second initialization
    initialize_database(conn)
    v2 = conn.execute("SELECT MAX(version) FROM schema_migrations;").fetchone()[0]
    assert v2 == 2

    # Check migration row count: exactly 2 rows
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations;").fetchone()[0]
    assert count == 2

    conn.close()


def test_concurrent_worker_unit_acquisition(tmp_path: Path) -> None:
    """Verify concurrent workers calling acquire_next_pending_unit get distinct units without collisions."""
    db_file = tmp_path / "concurrent_test.db"
    storage = TranslationStorage(db_file)

    job = TranslationJobRecord(
        job_id="concurrent-job",
        document_id="doc-conc",
        book_title="Concurrency Test Book",
        provider_name="gemini",
        model_name="gemini-3.5-flash-lite",
        total_units=6,
    )
    storage.create_job(job)

    # Insert 6 units in sequence
    units = [
        TranslationUnitRecord(
            unit_id=f"unit-{i}",
            job_id=job.job_id,
            sequence_order=i,
            content_hash=f"hash-{i}",
            source_original_text=f"Verse {i}",
        )
        for i in range(1, 7)
    ]
    storage.batch_upsert_units(units)

    def worker_acquire(worker_id: int) -> str | None:
        # Each worker thread calls acquire_next_pending_unit
        acquired = storage.acquire_next_pending_unit(job.job_id)
        return acquired.unit_id if acquired else None

    # Spawn 6 concurrent workers simultaneously
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(worker_acquire, i) for i in range(6)]
        results = [f.result() for f in futures]

    # Every worker must acquire a unique, non-None unit ID
    assert None not in results
    assert len(results) == 6
    assert len(set(results)) == 6  # Zero duplicate acquisitions!

    # A 7th acquire attempt must return None (no more PENDING units)
    extra = storage.acquire_next_pending_unit(job.job_id)
    assert extra is None


def test_approved_terminal_and_revocation_transitions() -> None:
    """Verify APPROVED state machine semantics: revocable to NEEDS_REVIEW, strictly forbidden to skip states."""
    # Revocation: APPROVED -> NEEDS_REVIEW is explicitly allowed for editorial revisions
    assert is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.NEEDS_REVIEW)

    # Direct jumps from APPROVED are forbidden
    assert not is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.PENDING)
    assert not is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.PROCESSING)
    assert not is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.TRANSLATED)
    assert not is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.QC_FAILED)
    assert not is_valid_unit_transition(UnitStatus.APPROVED, UnitStatus.QC_PASSED)

    with pytest.raises(InvalidStateTransitionError):
        validate_unit_transition(UnitStatus.APPROVED, UnitStatus.PENDING)

    with pytest.raises(InvalidStateTransitionError):
        validate_unit_transition(UnitStatus.APPROVED, UnitStatus.PROCESSING)

    # Job COMPLETED is strictly terminal
    assert not is_valid_job_transition(JobStatus.COMPLETED, JobStatus.RUNNING)
    assert not is_valid_job_transition(JobStatus.COMPLETED, JobStatus.INITIALIZED)
    assert not is_valid_job_transition(JobStatus.COMPLETED, JobStatus.FAILED)
