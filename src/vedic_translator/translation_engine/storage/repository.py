"""SQLite storage repository for translation jobs, units, and versioned drafts."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vedic_translator.core.exceptions import (
    RecordNotFoundError,
    StorageError,
)
from vedic_translator.translation_engine.storage.models import (
    JobStatus,
    TranslationJobRecord,
    TranslationUnitRecord,
    TranslationVersionRecord,
    UnitStatus,
    VersionStage,
)
from vedic_translator.translation_engine.storage.schema import initialize_database
from vedic_translator.translation_engine.storage.state_machine import (
    validate_job_transition,
    validate_unit_transition,
)


def _iso_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def _parse_datetime(val: str | None) -> datetime:
    """Safely parse ISO 8601 string to datetime."""
    if not val:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return datetime.now(UTC)


class TranslationStorage:
    """Thread-safe SQLite storage repository for translation jobs, units, and versions."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        """Initialize the storage repository and enforce schema migrations.

        Args:
            db_path: Path to SQLite database file or ':memory:' for transient storage.
        """
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._initialize()

    def _initialize(self) -> None:
        """Apply WAL mode and run migrations."""
        with self.get_connection() as conn:
            initialize_database(conn)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a database connection with row factory and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Translation Jobs
    # -------------------------------------------------------------------------

    def create_job(self, job: TranslationJobRecord) -> TranslationJobRecord:
        """Create a new translation job record in the database."""
        created_at_str = job.created_at.isoformat()
        updated_at_str = job.updated_at.isoformat()
        config_json = json.dumps(job.config, ensure_ascii=False)

        sql = """
        INSERT INTO translation_jobs (
            job_id, document_id, book_title, source_language, target_language,
            provider_name, model_name, status, total_units, completed_units,
            failed_units, config_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            with conn:
                try:
                    conn.execute(
                        sql,
                        (
                            job.job_id,
                            job.document_id,
                            job.book_title,
                            job.source_language,
                            job.target_language,
                            job.provider_name,
                            job.model_name,
                            job.status.value,
                            job.total_units,
                            job.completed_units,
                            job.failed_units,
                            config_json,
                            created_at_str,
                            updated_at_str,
                        ),
                    )
                except sqlite3.IntegrityError as e:
                    raise StorageError(
                        f"Job '{job.job_id}' already exists or violates constraint: {e}"
                    ) from e

        return job

    def get_job(self, job_id: str) -> TranslationJobRecord | None:
        """Retrieve a translation job by its unique identifier."""
        sql = "SELECT * FROM translation_jobs WHERE job_id = ?;"
        with self.get_connection() as conn:
            row = conn.execute(sql, (job_id,)).fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def update_job_status(self, job_id: str, new_status: JobStatus) -> TranslationJobRecord:
        """Update job status with strict state machine transition validation."""
        with self.get_connection() as conn:
            with conn:
                row = conn.execute(
                    "SELECT status FROM translation_jobs WHERE job_id = ?;", (job_id,)
                ).fetchone()
                if not row:
                    raise RecordNotFoundError(f"Translation job '{job_id}' not found.")

                current_status = JobStatus(row["status"])
                validate_job_transition(current_status, new_status)

                now_str = _iso_now()
                conn.execute(
                    "UPDATE translation_jobs SET status = ?, updated_at = ? WHERE job_id = ?;",
                    (new_status.value, now_str, job_id),
                )

        updated = self.get_job(job_id)
        if not updated:
            raise RecordNotFoundError(f"Translation job '{job_id}' not found after update.")
        return updated

    def update_job_progress(
        self,
        job_id: str,
        completed_increment: int = 0,
        failed_increment: int = 0,
        total_units: int | None = None,
    ) -> TranslationJobRecord:
        """Increment progress counts atomically for a job."""
        with self.get_connection() as conn:
            with conn:
                now_str = _iso_now()
                if total_units is not None:
                    conn.execute(
                        """
                        UPDATE translation_jobs
                        SET total_units = ?,
                            completed_units = completed_units + ?,
                            failed_units = failed_units + ?,
                            updated_at = ?
                        WHERE job_id = ?;
                        """,
                        (total_units, completed_increment, failed_increment, now_str, job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE translation_jobs
                        SET completed_units = completed_units + ?,
                            failed_units = failed_units + ?,
                            updated_at = ?
                        WHERE job_id = ?;
                        """,
                        (completed_increment, failed_increment, now_str, job_id),
                    )

        updated = self.get_job(job_id)
        if not updated:
            raise RecordNotFoundError(f"Translation job '{job_id}' not found.")
        return updated

    def list_jobs(self) -> list[TranslationJobRecord]:
        """List all registered translation jobs ordered by creation timestamp."""
        sql = "SELECT * FROM translation_jobs ORDER BY created_at DESC;"
        with self.get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [self._row_to_job(r) for r in rows]

    # -------------------------------------------------------------------------
    # Translation Units
    # -------------------------------------------------------------------------

    def upsert_unit(self, unit: TranslationUnitRecord) -> TranslationUnitRecord:
        """Idempotently insert or update a translation unit.

        - If the unit does not exist: inserts with status PENDING.
        - If the unit exists with identical content_hash: preserves existing status and progress.
        - If the unit exists with changed content_hash: updates source text, updates hash,
          and resets status to PENDING so the modified source is re-processed.
        """
        now_str = _iso_now()
        with self.get_connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT content_hash, status FROM translation_units WHERE unit_id = ?;",
                    (unit.unit_id,),
                ).fetchone()

                if not existing:
                    # New unit insert
                    conn.execute(
                        """
                        INSERT INTO translation_units (
                            unit_id, job_id, canonical_id, unit_type, sequence_order,
                            chapter_index, section_index, content_hash, source_original_text,
                            source_transliteration_text, source_reference_english,
                            source_commentary, status, attempts, last_error, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                            unit.source_transliteration_text,
                            unit.source_reference_english,
                            unit.source_commentary,
                            unit.status.value,
                            unit.attempts,
                            unit.last_error,
                            unit.created_at.isoformat(),
                            now_str,
                        ),
                    )
                else:
                    existing_hash = existing["content_hash"]
                    if existing_hash != unit.content_hash:
                        # Source text was modified: update source, reset attempts to 0, and reset to PENDING
                        logger.info(
                            f"Source content hash changed for unit {unit.unit_id}; resetting attempts to 0 and status to PENDING."
                        )
                        conn.execute(
                            """
                            UPDATE translation_units
                            SET content_hash = ?,
                                source_original_text = ?,
                                source_transliteration_text = ?,
                                source_reference_english = ?,
                                source_commentary = ?,
                                status = ?,
                                attempts = 0,
                                last_error = NULL,
                                updated_at = ?
                            WHERE unit_id = ?;
                            """,
                            (
                                unit.content_hash,
                                unit.source_original_text,
                                unit.source_transliteration_text,
                                unit.source_reference_english,
                                unit.source_commentary,
                                UnitStatus.PENDING.value,
                                now_str,
                                unit.unit_id,
                            ),
                        )
                    # If hash is identical, retain existing translation progress (idempotent!)

        saved = self.get_unit(unit.unit_id)
        if not saved:
            raise StorageError(f"Failed to upsert translation unit '{unit.unit_id}'.")
        return saved

    def batch_upsert_units(self, units: list[TranslationUnitRecord]) -> int:
        """Batch upsert multiple translation units within a single atomic transaction."""
        now_str = _iso_now()
        count = 0
        with self.get_connection() as conn:
            with conn:
                for unit in units:
                    existing = conn.execute(
                        "SELECT content_hash FROM translation_units WHERE unit_id = ?;",
                        (unit.unit_id,),
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            """
                            INSERT INTO translation_units (
                                unit_id, job_id, canonical_id, unit_type, sequence_order,
                                chapter_index, section_index, content_hash, source_original_text,
                                source_transliteration_text, source_reference_english,
                                source_commentary, status, attempts, last_error, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                                unit.source_transliteration_text,
                                unit.source_reference_english,
                                unit.source_commentary,
                                unit.status.value,
                                unit.attempts,
                                unit.last_error,
                                unit.created_at.isoformat(),
                                now_str,
                            ),
                        )
                        count += 1
                    else:
                        if existing["content_hash"] != unit.content_hash:
                            conn.execute(
                                """
                                UPDATE translation_units
                                SET content_hash = ?,
                                    source_original_text = ?,
                                    source_transliteration_text = ?,
                                    source_reference_english = ?,
                                    source_commentary = ?,
                                    status = ?,
                                    attempts = 0,
                                    last_error = NULL,
                                    updated_at = ?
                                WHERE unit_id = ?;
                                """,
                                (
                                    unit.content_hash,
                                    unit.source_original_text,
                                    unit.source_transliteration_text,
                                    unit.source_reference_english,
                                    unit.source_commentary,
                                    UnitStatus.PENDING.value,
                                    now_str,
                                    unit.unit_id,
                                ),
                            )
                            count += 1
        return count

    def get_unit(self, unit_id: str) -> TranslationUnitRecord | None:
        """Retrieve a single unit by its unit ID."""
        sql = "SELECT * FROM translation_units WHERE unit_id = ?;"
        with self.get_connection() as conn:
            row = conn.execute(sql, (unit_id,)).fetchone()
            if not row:
                return None
            return self._row_to_unit(row)

    def get_units_for_job(
        self, job_id: str, status: UnitStatus | None = None
    ) -> list[TranslationUnitRecord]:
        """Retrieve units for a job, optionally filtered by status, ordered by sequence."""
        if status is not None:
            sql = """
            SELECT * FROM translation_units
            WHERE job_id = ? AND status = ?
            ORDER BY sequence_order ASC;
            """
            params: tuple[Any, ...] = (job_id, status.value)
        else:
            sql = """
            SELECT * FROM translation_units
            WHERE job_id = ?
            ORDER BY sequence_order ASC;
            """
            params = (job_id,)

        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_unit(r) for r in rows]

    def update_unit_status(
        self,
        unit_id: str,
        new_status: UnitStatus,
        error_message: str | None = None,
        increment_attempts: bool = False,
        clear_error: bool = False,
    ) -> TranslationUnitRecord:
        """Update unit status with state machine validation and error tracking.

        Diagnostic integrity rules:
        - If error_message is provided: sets last_error to error_message.
        - If error_message is None:
            - When transitioning to a successful checkpoint state
              (TRANSLATED, QC_PASSED, APPROVED) or if clear_error=True: clears last_error to NULL.
            - When transitioning between error/review/pending states: preserves existing last_error.
        """
        success_states = {UnitStatus.TRANSLATED, UnitStatus.QC_PASSED, UnitStatus.APPROVED}
        with self.get_connection() as conn:
            with conn:
                row = conn.execute(
                    "SELECT status FROM translation_units WHERE unit_id = ?;", (unit_id,)
                ).fetchone()
                if not row:
                    raise RecordNotFoundError(f"Translation unit '{unit_id}' not found.")

                current_status = UnitStatus(row["status"])
                validate_unit_transition(current_status, new_status)

                now_str = _iso_now()
                attempts_clause = "attempts = attempts + 1," if increment_attempts else ""

                if error_message is not None:
                    error_clause = "last_error = ?,"
                    params: list[Any] = [new_status.value, error_message, now_str, unit_id]
                elif clear_error or new_status in success_states:
                    error_clause = "last_error = NULL,"
                    params = [new_status.value, now_str, unit_id]
                else:
                    error_clause = ""
                    params = [new_status.value, now_str, unit_id]

                sql = f"""
                UPDATE translation_units
                SET status = ?,
                    {attempts_clause}
                    {error_clause}
                    updated_at = ?
                WHERE unit_id = ?;
                """
                conn.execute(sql, tuple(params))

        updated = self.get_unit(unit_id)
        if not updated:
            raise RecordNotFoundError(f"Translation unit '{unit_id}' not found after update.")
        return updated

    def acquire_next_pending_unit(self, job_id: str) -> TranslationUnitRecord | None:
        """Atomically find the next PENDING unit in sequence and mark it PROCESSING.

        Uses an atomic single-statement UPDATE ... RETURNING clause to eliminate
        race conditions between concurrent workers.
        """
        now_str = _iso_now()
        sql = """
        UPDATE translation_units
        SET status = ?,
            attempts = attempts + 1,
            updated_at = ?
        WHERE unit_id = (
            SELECT unit_id FROM translation_units
            WHERE job_id = ? AND status = ?
            ORDER BY sequence_order ASC
            LIMIT 1
        )
        RETURNING *;
        """
        with self.get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    sql,
                    (
                        UnitStatus.PROCESSING.value,
                        now_str,
                        job_id,
                        UnitStatus.PENDING.value,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_unit(row)

    # -------------------------------------------------------------------------
    # Job Resumption and Crash Recovery
    # -------------------------------------------------------------------------

    def recover_interrupted_units(self, job_id: str) -> int:
        """Reset any units stuck in PROCESSING status back to PENDING after a crash or restart."""
        now_str = _iso_now()
        with self.get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE translation_units
                    SET status = ?,
                        last_error = 'Recovered from interrupted processing state',
                        updated_at = ?
                    WHERE job_id = ? AND status = ?;
                    """,
                    (UnitStatus.PENDING.value, now_str, job_id, UnitStatus.PROCESSING.value),
                )
                recovered_count = cursor.rowcount
                if recovered_count > 0:
                    logger.warning(
                        f"Recovered {recovered_count} interrupted units for job '{job_id}' back to PENDING."
                    )
                return recovered_count

    def get_job_statistics(self, job_id: str) -> dict[str, int]:
        """Return unit counts partitioned by their current lifecycle status."""
        sql = """
        SELECT status, COUNT(*) as count
        FROM translation_units
        WHERE job_id = ?
        GROUP BY status;
        """
        counts = {s.value: 0 for s in UnitStatus}
        with self.get_connection() as conn:
            rows = conn.execute(sql, (job_id,)).fetchall()
            for r in rows:
                counts[r["status"]] = r["count"]
        return counts

    # -------------------------------------------------------------------------
    # Translation Versions (Audit Trail)
    # -------------------------------------------------------------------------

    def create_version(
        self,
        unit_id: str,
        version: TranslationVersionRecord,
        new_unit_status: UnitStatus | None = None,
    ) -> TranslationVersionRecord:
        """Atomically persist a new translation version and optionally update unit status.

        Auto-increments version_number based on existing versions for this unit.
        Never overwrites earlier versions.
        """
        conf_json = (
            json.dumps(version.confidence_assessment, ensure_ascii=False)
            if version.confidence_assessment
            else None
        )
        qc_json = json.dumps(version.qc_results, ensure_ascii=False) if version.qc_results else None
        token_json = (
            json.dumps(version.token_usage, ensure_ascii=False) if version.token_usage else None
        )
        now_str = _iso_now()

        with self.get_connection() as conn:
            with conn:
                # 1. Verify unit exists
                unit_row = conn.execute(
                    "SELECT status FROM translation_units WHERE unit_id = ?;", (unit_id,)
                ).fetchone()
                if not unit_row:
                    raise RecordNotFoundError(
                        f"Cannot create translation version: unit '{unit_id}' does not exist."
                    )

                # 2. Determine next version number atomically
                cursor = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) FROM translation_versions WHERE unit_id = ?;",
                    (unit_id,),
                )
                max_ver = cursor.fetchone()[0]
                next_version_num = max_ver + 1

                # 3. Insert new version record
                conn.execute(
                    """
                    INSERT INTO translation_versions (
                        version_id, unit_id, version_number, source_stage,
                        translated_verse_russian, translated_commentary_russian,
                        translator_notes, confidence_assessment_json, qc_results_json,
                        token_usage_json, model_name, editor_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        version.version_id,
                        unit_id,
                        next_version_num,
                        version.source_stage.value,
                        version.translated_verse_russian,
                        version.translated_commentary_russian,
                        version.translator_notes,
                        conf_json,
                        qc_json,
                        token_json,
                        version.model_name,
                        version.editor_id,
                        version.created_at.isoformat(),
                    ),
                )

                # 4. Optionally update unit status within the same transaction
                if new_unit_status is not None:
                    current_status = UnitStatus(unit_row["status"])
                    validate_unit_transition(current_status, new_unit_status)
                    conn.execute(
                        "UPDATE translation_units SET status = ?, updated_at = ? WHERE unit_id = ?;",
                        (new_unit_status.value, now_str, unit_id),
                    )

        version.version_number = next_version_num
        return version

    def get_versions_for_unit(self, unit_id: str) -> list[TranslationVersionRecord]:
        """Retrieve all version records for a unit, ordered by version_number ascending."""
        sql = """
        SELECT * FROM translation_versions
        WHERE unit_id = ?
        ORDER BY version_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (unit_id,)).fetchall()
            return [self._row_to_version(r) for r in rows]

    def get_latest_version(self, unit_id: str) -> TranslationVersionRecord | None:
        """Retrieve the latest version record for a unit."""
        sql = """
        SELECT * FROM translation_versions
        WHERE unit_id = ?
        ORDER BY version_number DESC
        LIMIT 1;
        """
        with self.get_connection() as conn:
            row = conn.execute(sql, (unit_id,)).fetchone()
            if not row:
                return None
            return self._row_to_version(row)

    # -------------------------------------------------------------------------
    # Helper Mappers
    # -------------------------------------------------------------------------

    def _row_to_job(self, row: sqlite3.Row) -> TranslationJobRecord:
        """Map SQLite row to TranslationJobRecord."""
        config_data: dict[str, Any] = {}
        if row["config_json"]:
            try:
                config_data = json.loads(row["config_json"])
            except Exception:
                config_data = {}

        return TranslationJobRecord(
            job_id=row["job_id"],
            document_id=row["document_id"],
            book_title=row["book_title"],
            source_language=row["source_language"],
            target_language=row["target_language"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            status=JobStatus(row["status"]),
            total_units=row["total_units"],
            completed_units=row["completed_units"],
            failed_units=row["failed_units"],
            config=config_data,
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def _row_to_unit(self, row: sqlite3.Row) -> TranslationUnitRecord:
        """Map SQLite row to TranslationUnitRecord."""
        return TranslationUnitRecord(
            unit_id=row["unit_id"],
            job_id=row["job_id"],
            canonical_id=row["canonical_id"],
            unit_type=row["unit_type"],
            sequence_order=row["sequence_order"],
            chapter_index=row["chapter_index"],
            section_index=row["section_index"],
            content_hash=row["content_hash"],
            source_original_text=row["source_original_text"],
            source_transliteration_text=row["source_transliteration_text"],
            source_reference_english=row["source_reference_english"],
            source_commentary=row["source_commentary"],
            status=UnitStatus(row["status"]),
            attempts=row["attempts"],
            last_error=row["last_error"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def _row_to_version(self, row: sqlite3.Row) -> TranslationVersionRecord:
        """Map SQLite row to TranslationVersionRecord."""
        conf = (
            json.loads(row["confidence_assessment_json"])
            if row["confidence_assessment_json"]
            else None
        )
        qc = json.loads(row["qc_results_json"]) if row["qc_results_json"] else None
        token = json.loads(row["token_usage_json"]) if row["token_usage_json"] else None

        return TranslationVersionRecord(
            version_id=row["version_id"],
            unit_id=row["unit_id"],
            version_number=row["version_number"],
            source_stage=VersionStage(row["source_stage"]),
            translated_verse_russian=row["translated_verse_russian"],
            translated_commentary_russian=row["translated_commentary_russian"],
            translator_notes=row["translator_notes"],
            confidence_assessment=conf,
            qc_results=qc,
            token_usage=token,
            model_name=row["model_name"],
            editor_id=row["editor_id"],
            created_at=_parse_datetime(row["created_at"]),
        )
