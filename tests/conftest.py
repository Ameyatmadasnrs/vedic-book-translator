"""Pytest fixtures for Vedic Book Translator test suite."""

from pathlib import Path
import pytest

from vedic_translator.core.models import (
    Block,
    BlockState,
    BlockType,
    Chapter,
    Document,
    DocumentMetadata,
    Section,
)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_verse_block() -> Block:
    """Create a sample Block fixture representing a Sanskrit verse."""
    return Block(
        type=BlockType.VERSE_IAST,
        source_text="dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā\ntathā dehāntara-prāptir dhīras tatra na muhyati",
        verse_number="2.13",
        sequence_index=1,
    )


@pytest.fixture
def sample_document() -> Document:
    """Create a sample minimal Document AST."""
    metadata = DocumentMetadata(
        title="Bhagavad-gita As It Is",
        author="A.C. Bhaktivedanta Swami Prabhupada",
        source_language="en",
        target_language="ru",
    )
    doc = Document(metadata=metadata)
    chapter = Chapter(chapter_index=2, title="Contents of the Gita Summarized")
    section = Section(section_index=13, verse_range="2.13")
    
    section.blocks.extend([
        Block(
            type=BlockType.VERSE_DEVANAGARI,
            source_text="देहिनोऽस्मिन्यथा देहे कौमारं यौवनं जरा ।\nतथा देहान्तरप्राप्तिर्धीरस्तत्र न मुह्यति ॥ १३ ॥",
            verse_number="2.13",
            sequence_index=0,
        ),
        Block(
            type=BlockType.VERSE_IAST,
            source_text="dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā\ntathā dehāntara-prāptir dhīras tatra na muhyati",
            verse_number="2.13",
            sequence_index=1,
        ),
        Block(
            type=BlockType.SYNONYMS,
            source_text="dehinaḥ — of the embodied; asmin — in this; yathā — as; dehe — in the body; kaumāram — boyhood; yauvanam — youth; jarā — old age; tathā — similarly; dehāntara — of another body; prāptiḥ — achievement; dhīraḥ — the sober; tatra — thereupon; na — never; muhyati — is deluded.",
            verse_number="2.13",
            sequence_index=2,
        ),
        Block(
            type=BlockType.TRANSLATION,
            source_text="As the embodied soul continuously passes, in this body, from boyhood to youth to old age, the soul similarly passes into another body at death. A sober person is not bewildered by such a change.",
            verse_number="2.13",
            sequence_index=3,
        ),
        Block(
            type=BlockType.PURPORT,
            source_text="Since every living entity is an individual soul, each is changing his body every moment...",
            verse_number="2.13",
            sequence_index=4,
        ),
    ])
    
    chapter.sections.append(section)
    doc.chapters.append(chapter)
    return doc
