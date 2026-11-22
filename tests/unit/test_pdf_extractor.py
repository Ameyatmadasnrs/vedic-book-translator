"""Unit tests for PDFExtractor."""

from pathlib import Path

import pymupdf as fitz
import pytest

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    UnsupportedFormatError,
)
from vedic_translator.document_processor.extractors.pdf import PDFExtractor


def test_pdf_extractor_supports() -> None:
    extractor = PDFExtractor()
    assert extractor.supports(Path("gita.pdf"))
    assert not extractor.supports(Path("gita.epub"))


def test_pdf_extractor_valid_digital_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "digital_gita.pdf"
    doc = fitz.open()

    nirmala_font = "C:/Windows/Fonts/Nirmala.ttc"
    has_nirmala = Path(nirmala_font).exists()

    # Page 1
    page1 = doc.new_page()
    if has_nirmala:
        page1.insert_font(fontname="nirmala", fontfile=nirmala_font)
        page1.insert_text((50, 72), "Chapter 1: The Battlefield of Kurukshetra", fontsize=16)
        page1.insert_text(
            (50, 100), "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।", fontname="nirmala", fontsize=12
        )
        page1.insert_text((50, 130), "dharma-kṣetre kuru-kṣetre samavetā yuyutsavaḥ", fontsize=12)
        page1.insert_text((50, 160), "О Санджая, собравшись на священном поле...", fontsize=12)
    else:
        page1.insert_text((50, 72), "Chapter 1: The Battlefield of Kurukshetra", fontsize=16)
        page1.insert_text((50, 100), "dharma-ksetre kuru-ksetre samaveta yuyutsavah", fontsize=12)

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Chapter 2: Contents of the Gita", fontsize=16)
    page2.insert_text((50, 100), "dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā", fontsize=12)

    # Set metadata and TOC
    doc.set_metadata({"title": "Bhagavad-gita As It Is", "author": "Srila Prabhupada"})
    doc.set_toc(
        [
            [1, "Chapter 1: The Battlefield of Kurukshetra", 1],
            [1, "Chapter 2: Contents of the Gita", 2],
        ]
    )

    doc.save(str(pdf_path))
    doc.close()

    extractor = PDFExtractor()
    ast_doc = extractor.extract(pdf_path)

    assert ast_doc.metadata.title == "Bhagavad-gita As It Is"
    assert ast_doc.metadata.author == "Srila Prabhupada"
    assert len(ast_doc.chapters) == 2

    ch1 = ast_doc.chapters[0]
    assert "Chapter 1" in ch1.title
    all_text = " ".join(
        b.source_text for ch in ast_doc.chapters for s in ch.sections for b in s.blocks
    )
    if has_nirmala:
        assert "धर्मक्षेत्रे" in all_text
    assert "dehino 'smin" in all_text


def test_pdf_extractor_scanned_empty_pdf(tmp_path: Path) -> None:
    # A PDF with a page but zero text blocks (simulating scanned/image-only PDF)
    empty_pdf_path = tmp_path / "scanned_empty.pdf"
    doc = fitz.open()
    doc.new_page()  # Blank page with no text
    doc.save(str(empty_pdf_path))
    doc.close()

    extractor = PDFExtractor()
    with pytest.raises(CorruptedDocumentError) as exc_info:
        extractor.extract(empty_pdf_path)
    assert "no digital text layer" in str(exc_info.value)


def test_pdf_extractor_corrupted_file(tmp_path: Path) -> None:
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4 completely corrupt garbage")

    extractor = PDFExtractor()
    with pytest.raises(CorruptedDocumentError):
        extractor.extract(corrupt_pdf)


def test_pdf_extractor_unsupported_format(tmp_path: Path) -> None:
    docx_file = tmp_path / "test.docx"
    docx_file.write_bytes(b"dummy")

    extractor = PDFExtractor()
    with pytest.raises(UnsupportedFormatError):
        extractor.extract(docx_file)


def test_pdf_extractor_preserves_non_breaking_spaces(tmp_path: Path) -> None:
    """Verify PDFExtractor preserves exact U+00A0 in source_text and provides U+0020 in normalized_text."""
    pdf_path = tmp_path / "non_breaking.pdf"
    doc = fitz.open()
    page = doc.new_page()

    arial_font = "C:/Windows/Fonts/arial.ttf"
    has_arial = Path(arial_font).exists()

    if has_arial:
        page.insert_font(fontname="arial", fontfile=arial_font)
        # Arial insertion with fitz encodes inter-word spacing as \xa0
        page.insert_text((50, 72), "Chapter 1: The Spiritual Master", fontname="arial", fontsize=14)
        page.insert_text(
            (50, 110),
            "Введение: Шрила Прабхупада является ачарьей-основателем.",
            fontname="arial",
            fontsize=12,
        )
    else:
        page.insert_text((50, 72), "Chapter 1: The Spiritual Master", fontsize=14)
        page.insert_text(
            (50, 110),
            "Введение: Шрила Прабхупада является ачарьей-основателем.",
            fontsize=12,
        )

    doc.save(str(pdf_path))
    doc.close()

    extractor = PDFExtractor()
    ast_doc = extractor.extract(pdf_path)

    assert len(ast_doc.chapters) >= 1
    blocks = [b for ch in ast_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(blocks) >= 1

    # Check that normalized_text always replaces \xa0 with standard space \x20
    for block in blocks:
        assert "\xa0" not in block.normalized_text

    # If Arial was used, fitz emits \xa0; verify that source_text preserved \xa0 verbatim
    if has_arial:
        raw_source_texts = " ".join(b.source_text for b in blocks)
        normalized_texts = " ".join(b.normalized_text for b in blocks)

        assert "\xa0" in raw_source_texts
        assert "\xa0" not in normalized_texts
        assert "The Spiritual Master" in normalized_texts
        assert "Шрила Прабхупада" in normalized_texts
