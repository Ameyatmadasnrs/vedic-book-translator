"""Canonical Document Abstract Syntax Tree (AST) models for Vedic Book Translator.

Built with Pydantic v2 for strict type safety and high-performance serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    """Categorization of semantic text blocks."""
    VERSE_DEVANAGARI = "VERSE_DEVANAGARI"
    VERSE_IAST = "VERSE_IAST"
    SYNONYMS = "SYNONYMS"
    TRANSLATION = "TRANSLATION"
    PURPORT = "PURPORT"
    HEADING = "HEADING"
    SUBHEADING = "SUBHEADING"
    PARAGRAPH = "PARAGRAPH"
    FOOTNOTE = "FOOTNOTE"
    QUOTE = "QUOTE"


class BlockState(str, Enum):
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None


class AuditFinding(BaseModel):
    """Specific finding from automated quality control."""
    rule_name: str
    severity: str = "ERROR"  # "ERROR", "WARNING", "INFO"
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class AuditResult(BaseModel):
    """Summary of automated quality control checks on a block."""
    passed: bool
    findings: List[AuditFinding] = Field(default_factory=list)
    terminology_fidelity_score: float = 100.0
    diacritics_completeness_score: float = 100.0
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class Block(BaseModel):
    """Atomic unit of document structure and translation."""
    id: UUID = Field(default_factory=uuid4)
    type: BlockType
    source_text: str
    target_text: Optional[str] = None
    state: BlockState = BlockState.INGESTED
    verse_number: Optional[str] = None
    sequence_index: int = 0
    history: List[StageAudit] = Field(default_factory=list)
    audit_result: Optional[AuditResult] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Section(BaseModel):
    """A logical section within a chapter (e.g., a single verse with commentary)."""
    id: UUID = Field(default_factory=uuid4)
    section_index: int
    heading: Optional[str] = None
    verse_range: Optional[str] = None
    blocks: List[Block] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChapterSummary(BaseModel):
    """Contextual summary of a chapter used for narrative continuity."""
    summary_text: str = ""
    key_philosophical_points: List[str] = Field(default_factory=list)
    entities_present: List[str] = Field(default_factory=list)


class Chapter(BaseModel):
    """A major chapter or canto division of a book."""
    id: UUID = Field(default_factory=uuid4)
    chapter_index: int
    title: str
    sections: List[Section] = Field(default_factory=list)
    summary: Optional[ChapterSummary] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Bibliographic and technical metadata for the work."""
    title: str
    author: Optional[str] = None
    commentator: Optional[str] = None
    source_language: str = "en"
    target_language: str = "ru"
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    original_file_name: Optional[str] = None
    original_file_hash: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class DocumentStatus(str, Enum):
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
    chapters: List[Chapter] = Field(default_factory=list)
    status: DocumentStatus = DocumentStatus.INGESTED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def total_blocks(self) -> int:
        """Calculate total number of semantic blocks in the document."""
        return sum(
            len(section.blocks)
            for chapter in self.chapters
            for section in chapter.sections
        )

    def completed_blocks(self) -> int:
        """Calculate total number of completed / approved blocks."""
        return sum(
            1
            for chapter in self.chapters
            for section in chapter.sections
            for block in section.blocks
            if block.state in (BlockState.QC_VERIFIED, BlockState.APPROVED)
        )
