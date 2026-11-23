"""Canonical Document Abstract Syntax Tree (AST) models for Vedic Book Translator.

Built with Pydantic v2 for strict type safety and high-performance serialization.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


class BlockType(StrEnum):
    """Categorization of semantic text blocks."""

    # Universal structural & content blocks
    HEADING = "HEADING"
    SUBHEADING = "SUBHEADING"
    PARAGRAPH = "PARAGRAPH"
    BLOCKQUOTE = "BLOCKQUOTE"
    QUOTE = "QUOTE"  # Backward compatibility alias for BLOCKQUOTE
    EPIGRAPH = "EPIGRAPH"
    LIST_ITEM = "LIST_ITEM"
    TABLE = "TABLE"
    FOOTNOTE = "FOOTNOTE"
    THEMATIC_BREAK = "THEMATIC_BREAK"
    CAPTION = "CAPTION"

    # Specialized commentary & scripture content elements (Phase 1.1 + future stages)
    VERSE_DEVANAGARI = "VERSE_DEVANAGARI"
    VERSE_IAST = "VERSE_IAST"
    SYNONYMS = "SYNONYMS"
    TRANSLATION = "TRANSLATION"
    PURPORT = "PURPORT"


class BlockState(StrEnum):
    """Lifecycle state of a translation block."""

    INGESTED = "INGESTED"
    STAGE_1_LITERAL = "STAGE_1_LITERAL"
    STAGE_2_PHILOSOPHICAL = "STAGE_2_PHILOSOPHICAL"
    STAGE_3_LITERARY = "STAGE_3_LITERARY"
    STAGE_4_TERMINOLOGY = "STAGE_4_TERMINOLOGY"
    QC_VERIFIED = "QC_VERIFIED"
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"
    APPROVED = "APPROVED"


class StageAudit(BaseModel):
    """Record of a single transformation stage execution."""

    stage_name: str
    model_used: str
    input_text: str
    output_text: str
    latency_ms: float
    timestamp: datetime = Field(default_factory=utc_now)
    notes: str | None = None


class AuditFinding(BaseModel):
    """Specific finding from automated quality control."""

    rule_name: str
    severity: str = "ERROR"  # "ERROR", "WARNING", "INFO"
    message: str
    expected: str | None = None
    actual: str | None = None


class AuditResult(BaseModel):
    """Summary of automated quality control checks on a block."""

    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)
    terminology_fidelity_score: float = 100.0
    diacritics_completeness_score: float = 100.0
    evaluated_at: datetime = Field(default_factory=utc_now)


class AlternativeClassification(BaseModel):
    """Alternative classification candidate with confidence and rationale."""

    suggested_type: BlockType
    confidence: float  # Bounded in [0.0, 1.0]
    rule_name: str
    reason: str


class ClassificationProvenance(BaseModel):
    """Audit provenance for how a block was classified."""

    method: str  # e.g., "format_native", "heuristic_rule", "ai_fallback", "manual"
    rule_name: str  # e.g., "docx_heading_style", "markdown_blockquote"
    confidence: float  # Bounded in [0.0, 1.0]
    alternatives: list[AlternativeClassification] = Field(default_factory=list)
    applied_at: datetime = Field(default_factory=utc_now)


class Block(BaseModel):
    """Atomic unit of document structure and translation."""

    id: UUID = Field(default_factory=uuid4)
    type: BlockType
    source_text: str
    target_text: str | None = None
    state: BlockState = BlockState.INGESTED
    verse_number: str | None = None
    sequence_index: int = 0
    history: list[StageAudit] = Field(default_factory=list)
    audit_result: AuditResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: ClassificationProvenance | None = None
    alternative_classifications: list[AlternativeClassification] = Field(default_factory=list)
    verse_unit_ids: list[UUID] = Field(default_factory=list)

    @property
    def normalized_text(self) -> str:
        """Return source text with non-breaking spaces (U+00A0) replaced by regular spaces (U+0020).

        Preserves verbatim source_text while providing a normalized representation
        for search, indexing, tokenization, and semantic comparisons.
        """
        return self.source_text.replace("\xa0", " ")


class VerseUnitType(StrEnum):
    """Metrical or functional classification of scripture unit."""

    SLOKA = "SLOKA"  # Classical Sanskrit verse (Anushtubh, etc.)
    DOHA = "DOHA"  # Awadhi / Hindi rhyming couplet
    CHAUPAI = "CHAUPAI"  # Awadhi / Hindi 4-line stanza (16 matras)
    SORATHA = "SORATHA"  # Inverted doha meter
    CHHANDA = "CHHANDA"  # Metrical hymn / stotra
    MANTRA = "MANTRA"  # Vedic Samhita / Upanishadic prose-verse
    PROSE_SECTION = "PROSE_SECTION"  # Pure narrative / introductory prose
    GENERIC_VERSE = "GENERIC_VERSE"  # Universal metrical / poetic unit


class RoutingAction(StrEnum):
    """Provisional editorial routing decision."""

    AUTO_ACCEPTED = "AUTO_ACCEPTED"  # High confidence; ready for translation
    AMBIGUOUS = "AMBIGUOUS"  # Medium confidence; candidate linked, flagged for QA
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"  # Low confidence; unforced, requires human sign-off


class RelationshipConfidence(BaseModel):
    """Provisional structural heuristic confidence score and diagnostic audit trail."""

    overall_score: float = Field(ge=0.0, le=1.0)
    component_scores: dict[str, float] = Field(default_factory=dict)
    routing_action: RoutingAction = RoutingAction.AUTO_ACCEPTED
    provenance_rules: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class VerseUnit(BaseModel):
    """Optional logical grouping of blocks representing a verse and its commentary apparatus."""

    id: UUID = Field(default_factory=uuid4)
    unit_type: VerseUnitType = VerseUnitType.GENERIC_VERSE
    canonical_id: str | None = None  # e.g., "1.188", "Cau. 1.188.1", "Do. 2 (A)"
    verse_range: str | None = None  # e.g., "1.21-1.22" for composite multi-verse units

    # List-based references to constituent blocks (strictly in reading order)
    original_script_block_ids: list[UUID] = Field(default_factory=list)
    transliteration_block_ids: list[UUID] = Field(default_factory=list)
    synonyms_block_ids: list[UUID] = Field(default_factory=list)
    translation_block_ids: list[UUID] = Field(default_factory=list)
    commentary_block_ids: list[UUID] = Field(default_factory=list)
    footnote_block_ids: list[UUID] = Field(default_factory=list)

    # Incompleteness tracking
    is_complete: bool = True
    missing_components: list[str] = Field(default_factory=list)

    # Confidence and audit routing
    confidence: RelationshipConfidence
    metadata: dict[str, Any] = Field(default_factory=dict)

    def all_block_ids(self) -> list[UUID]:
        """Return all referenced block UUIDs in logical reading sequence."""
        return (
            self.original_script_block_ids
            + self.transliteration_block_ids
            + self.synonyms_block_ids
            + self.translation_block_ids
            + self.commentary_block_ids
            + self.footnote_block_ids
        )


class Section(BaseModel):
    """A logical section within a chapter (e.g., a single verse with commentary)."""

    id: UUID = Field(default_factory=uuid4)
    section_index: int
    heading: str | None = None
    verse_range: str | None = None
    blocks: list[Block] = Field(default_factory=list)
    verse_units: list[VerseUnit] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterSummary(BaseModel):
    """Contextual summary of a chapter used for narrative continuity."""

    summary_text: str = ""
    key_philosophical_points: list[str] = Field(default_factory=list)
    entities_present: list[str] = Field(default_factory=list)


class Chapter(BaseModel):
    """A major chapter or canto division of a book."""

    id: UUID = Field(default_factory=uuid4)
    chapter_index: int
    title: str
    sections: list[Section] = Field(default_factory=list)
    summary: ChapterSummary | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Bibliographic and technical metadata for the work."""

    title: str
    author: str | None = None
    commentator: str | None = None
    source_language: str = "en"
    target_language: str = "ru"
    isbn: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    original_file_name: str | None = None
    original_file_hash: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class DocumentStatus(StrEnum):
    """Overall status of a document translation job."""

    INGESTED = "INGESTED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(BaseModel):
    """The root canonical Document AST node."""

    id: UUID = Field(default_factory=uuid4)
    metadata: DocumentMetadata
    chapters: list[Chapter] = Field(default_factory=list)
    status: DocumentStatus = DocumentStatus.INGESTED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def total_blocks(self) -> int:
        """Calculate total number of semantic blocks in the document."""
        return sum(len(section.blocks) for chapter in self.chapters for section in chapter.sections)

    def completed_blocks(self) -> int:
        """Calculate total number of completed / approved blocks."""
        return sum(
            1
            for chapter in self.chapters
            for section in chapter.sections
            for block in section.blocks
            if block.state in (BlockState.QC_VERIFIED, BlockState.APPROVED)
        )
