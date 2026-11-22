"""Integration tests for DocumentExtractor facade and non-destructive ingestion."""

from pathlib import Path
import docx
import pymupdf as fitz
import pytest

from vedic_translator.core.exceptions import UnsupportedFormatError
from vedic_translator.document_processor.extractors import (
    DocumentExtractor,
    compute_file_sha256,
)


def test_extractor_non_destructive_guarantee(tmp_path: Path) -> None:
    """Verify that source documents are strictly read-only and never modified."""
    txt_file = tmp_path / "sacred_text.txt"
    original_content = (
        "# Sri Brahma Samhita\n\n"
        "ईश्वरः परमः कृष्णः सच्चिदानन्दविग्रहः ।\n"
        "अनादिरादिर्गोविन्दः सर्वकारणकारणम् ॥ १ ॥\n\n"
        "īśvaraḥ paramaḥ kṛṣṇaḥ sac-cid-ānanda-vigrahaḥ\n"
        "anādir ādir govindaḥ sarva-kāraṇa-kāraṇam\n\n"
        "Кришна, известный как Говинда — это Верховная Личность Бога...\n"
    )
    txt_file.write_text(original_content, encoding="utf-8")
    initial_sha = compute_file_sha256(txt_file)
    initial_mtime = txt_file.stat().st_mtime

    extractor = DocumentExtractor()
    doc = extractor.extract(txt_file)

    # Assert AST was generated
    assert doc.metadata.title == "Sri Brahma Samhita"
    assert doc.total_blocks() > 0

    # Assert source file was completely untouched
    final_sha = compute_file_sha256(txt_file)
    final_mtime = txt_file.stat().st_mtime
    assert initial_sha == final_sha
    assert initial_mtime == final_mtime
    assert txt_file.read_text(encoding="utf-8") == original_content


def test_extractor_multi_format_dispatch(tmp_path: Path) -> None:
    """Verify that DocumentExtractor routes each format to the correct extractor."""
    extractor = DocumentExtractor()

    # 1. TXT
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("# Chapter 1\n\nSome text", encoding="utf-8")
    doc_txt = extractor.extract(txt_file)
    assert doc_txt.metadata.original_file_name == "test.txt"

    # 2. DOCX
    docx_file = tmp_path / "test.docx"
    d = docx.Document()
    d.add_heading("Chapter 1", level=1)
    d.add_paragraph("Docx paragraph")
    d.save(str(docx_file))
    doc_docx = extractor.extract(docx_file)
    assert doc_docx.metadata.original_file_name == "test.docx"

    # 3. PDF
    pdf_file = tmp_path / "test.pdf"
    p = fitz.open()
    page = p.new_page()
    page.insert_text((50, 72), "PDF text")
    p.save(str(pdf_file))
    p.close()
    doc_pdf = extractor.extract(pdf_file)
    assert doc_pdf.metadata.original_file_name == "test.pdf"


def test_extractor_file_not_found() -> None:
    extractor = DocumentExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract(Path("non_existent_file_xyz.pdf"))


def test_extractor_unsupported_extension(tmp_path: Path) -> None:
    unsupported = tmp_path / "audio.mp3"
    unsupported.write_bytes(b"dummy audio")
    extractor = DocumentExtractor()
    with pytest.raises(UnsupportedFormatError):
        extractor.extract(unsupported)
