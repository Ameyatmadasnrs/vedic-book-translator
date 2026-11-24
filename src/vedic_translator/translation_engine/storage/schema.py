"""SQLite schema definition, indexing, and versioned migration engine."""

import sqlite3
from datetime import UTC, datetime

CURRENT_SCHEMA_VERSION = 2

MIGRATION_V1_SQL = """
-- Version 1: Core Job, Unit, and Version Tables

CREATE TABLE IF NOT EXISTS translation_jobs (
    job_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    book_title TEXT NOT NULL,
    source_language TEXT NOT NULL DEFAULT 'awa',
    target_language TEXT NOT NULL DEFAULT 'ru',
    provider_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('INITIALIZED', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED')),
    total_units INTEGER NOT NULL DEFAULT 0,
    completed_units INTEGER NOT NULL DEFAULT 0,
    failed_units INTEGER NOT NULL DEFAULT 0,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS translation_units (
    unit_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES translation_jobs(job_id) ON DELETE CASCADE,
    canonical_id TEXT,
    unit_type TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    chapter_index INTEGER NOT NULL,
    section_index INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    source_original_text TEXT NOT NULL,
    source_transliteration_text TEXT,
    source_reference_english TEXT,
    source_commentary TEXT,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'PROCESSING', 'TRANSLATED', 'QC_FAILED', 'QC_PASSED', 'NEEDS_REVIEW', 'APPROVED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_units_job_status ON translation_units(job_id, status);
CREATE INDEX IF NOT EXISTS idx_units_content_hash ON translation_units(content_hash);
CREATE INDEX IF NOT EXISTS idx_units_sequence ON translation_units(sequence_order);
CREATE INDEX IF NOT EXISTS idx_units_job_seq ON translation_units(job_id, sequence_order);

CREATE TABLE IF NOT EXISTS translation_versions (
    version_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL REFERENCES translation_units(unit_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    source_stage TEXT NOT NULL CHECK(source_stage IN ('AI_DRAFT', 'HUMAN_EDIT', 'RETRANSLATION')),
    translated_verse_russian TEXT NOT NULL,
    translated_commentary_russian TEXT,
    translator_notes TEXT,
    confidence_assessment_json TEXT,
    qc_results_json TEXT,
    token_usage_json TEXT,
    model_name TEXT,
    editor_id TEXT,
    created_at TEXT NOT NULL,
    CONSTRAINT uq_unit_version UNIQUE (unit_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_versions_unit_num ON translation_versions(unit_id, version_number);
CREATE INDEX IF NOT EXISTS idx_versions_created ON translation_versions(created_at);
"""

MIGRATION_V2_SQL = """
-- Version 2: Composite index for sequential pending unit acquisition
CREATE INDEX IF NOT EXISTS idx_units_job_status_seq
ON translation_units(job_id, status, sequence_order);
"""

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Initial schema: translation_jobs, translation_units, translation_versions",
        MIGRATION_V1_SQL,
    ),
    (
        2,
        "Add composite index idx_units_job_status_seq for sequential unit acquisition",
        MIGRATION_V2_SQL,
    ),
]


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize WAL mode, foreign keys, migrations table, and apply pending migrations."""
    # Enforce SQLite WAL mode and foreign key constraints
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    # Ensure schema migrations table exists
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT NOT NULL
        );
        """
    )
    conn.commit()

    # Determine currently applied version
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations;")
    row = cursor.fetchone()
    current_version = row[0] if row else 0

    # Apply any pending migrations in a single transaction
    with conn:
        for version, description, sql in MIGRATIONS:
            if version > current_version:
                conn.executescript(sql)
                applied_at = datetime.now(UTC).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?);",
                    (version, applied_at, description),
                )
