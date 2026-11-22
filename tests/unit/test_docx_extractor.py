"""Unit tests for DOCXExtractor."""

from pathlib import Path
import docx
import pytest

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    UnsupportedFormatError,
)
from vedic_translator.core.models import BlockType
from vedic_translator.document_processor.extractors.docx import DOCXExtractor


def test_docx_extractor_supports() -> None:
    extractor = DOCXExtractor()
    assert extractor.supports(Path("book.docx"))
    assert not extractor.supports(Path("book.pdf"))


def test_docx_extractor_valid_document(tmp_path: Path) -> None:
    docx_file = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.core_properties.title = "Bhagavad Gita As It Is"
    doc.core_properties.author = "A.C. Bhaktivedanta Swami Prabhupada"

    # Add Chapter 1
    doc.add_heading("Chapter 1: Setting the Scene", level=1)
    doc.add_paragraph("dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā")
    doc.add_paragraph("Воплотившаяся душа постепенно меняет тело отрочества на тело юности...")

    # Add Chapter 2
    doc.add_heading("Chapter 2: Transcendental Knowledge", level=1)
    doc.add_paragraph("न जायते म्रियते वा कदाचिन्")

    doc.save(str(docx_file))

    extractor = DOCXExtractor()
    ast_doc = extractor.extract(docx_file)

    assert ast_doc.metadata.title == "Bhagavad Gita As It Is"
    assert ast_doc.metadata.author == "A.C. Bhaktivedanta Swami Prabhupada"
    assert len(ast_doc.chapters) == 2

    ch1 = ast_doc.chapters[0]
    assert ch1.chapter_index == 1
    assert "Chapter 1" in ch1.title

    ch2 = ast_doc.chapters[1]
    assert ch2.chapter_index == 2
    assert "Chapter 2" in ch2.title

    all_text = " ".join(b.source_text for ch in ast_doc.chapters for s in ch.sections for b in s.blocks)
    assert "dehino 'smin" in all_text
    assert "Воплотившаяся душа" in all_text
    assert "न जायते" in all_text


def test_docx_extractor_corrupted_file(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.docx"
    corrupt_file.write_bytes(b"PK\x03\x04This is not a real docx zip archive!")

    extractor = DOCXExtractor()
    with pytest.raises(CorruptedDocumentError):
        extractor.extract(corrupt_file)


def test_docx_extractor_unsupported_format(tmp_path: Path) -> None:
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("dummy", encoding="utf-8")

    extractor = DOCXExtractor()
    with pytest.raises(UnsupportedFormatError):
        extractor.extract(txt_file)
