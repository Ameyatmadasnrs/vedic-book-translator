"""Unit tests for Vedic Book Translator core models and exceptions."""

import pytest
from vedic_translator.core.models import (
    Block,
    BlockState,
    BlockType,
    Chapter,
    Document,
    DocumentMetadata,
    DocumentStatus,
    Section,
    StageAudit,
)
from vedic_translator.core.exceptions import (
    VedicTranslatorError,
    IngestionError,
    TerminologyViolationError,
)


def test_block_creation_and_defaults(sample_verse_block: Block) -> None:
    """Test creating a Block with defaults and attributes."""
    assert sample_verse_block.type == BlockType.VERSE_IAST
    assert sample_verse_block.state == BlockState.INGESTED
    assert sample_verse_block.verse_number == "2.13"
    assert len(sample_verse_block.history) == 0
    assert sample_verse_block.target_text is None


def test_block_history_recording(sample_verse_block: Block) -> None:
    """Test adding audit stage execution history to a block."""
    audit = StageAudit(
        stage_name="STAGE_1_LITERAL",
        model_used="gemini-2.5-pro",
        input_text=sample_verse_block.source_text,
        output_text="Воплотившаяся душа...",
        latency_ms=450.5,
    )
    sample_verse_block.history.append(audit)
    sample_verse_block.state = BlockState.STAGE_1_LITERAL
    
    assert len(sample_verse_block.history) == 1
    assert sample_verse_block.history[0].stage_name == "STAGE_1_LITERAL"
    assert sample_verse_block.state == BlockState.STAGE_1_LITERAL


def test_document_ast_structure(sample_document: Document) -> None:
    """Test hierarchical integrity of Document AST."""
    assert sample_document.metadata.title == "Bhagavad-gita As It Is"
    assert sample_document.status == DocumentStatus.INGESTED
    assert len(sample_document.chapters) == 1
    
    chapter = sample_document.chapters[0]
    assert chapter.chapter_index == 2
    assert len(chapter.sections) == 1
    
    section = chapter.sections[0]
    assert section.verse_range == "2.13"
    assert len(section.blocks) == 5
    
    # Check block types ordering
    expected_types = [
        BlockType.VERSE_DEVANAGARI,
        BlockType.VERSE_IAST,
        BlockType.SYNONYMS,
        BlockType.TRANSLATION,
        BlockType.PURPORT,
    ]
    actual_types = [block.type for block in section.blocks]
    assert actual_types == expected_types

    assert sample_document.total_blocks() == 5
    assert sample_document.completed_blocks() == 0


def test_document_serialization(sample_document: Document) -> None:
    """Test serialization to JSON and deserialization back."""
    json_data = sample_document.model_dump_json()
    assert isinstance(json_data, str)
    
    restored_doc = Document.model_validate_json(json_data)
    assert restored_doc.id == sample_document.id
    assert restored_doc.metadata.title == sample_document.metadata.title
    assert restored_doc.total_blocks() == 5


def test_custom_exception_hierarchy() -> None:
    """Test exception hierarchy and string representations."""
    err = TerminologyViolationError(
        "Forbidden Mayavada translation detected",
        details={"term": "Brahman", "translation_found": "Cosmic Mind"},
    )
    assert isinstance(err, VedicTranslatorError)
    assert "Forbidden Mayavada translation detected" in str(err)
    assert "Cosmic Mind" in str(err)
