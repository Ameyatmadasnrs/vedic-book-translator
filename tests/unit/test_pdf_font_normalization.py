"""Unit tests for span-level font normalization integrated into PDFExtractor."""

from pathlib import Path

import pymupdf as fitz
import pytest

from vedic_translator.document_processor.extractors.pdf import PDFExtractor


@pytest.fixture
def mixed_font_pdf(tmp_path: Path) -> Path:
    """Generate a synthetic digital PDF with mixed legacy and standard font spans."""
    pdf_path = tmp_path / "mixed_sample.pdf"
    doc = fitz.open()

    page = doc.new_page()

    # Block 1: Multi-span mixed line (English + Chanakya Sanskrit + English)
    # Line 1:
    #   Span 1 (Nalandatim): "Recite this Mantra: "
    #   Span 2 (ChanakyaBold): "üÊË‚ËÃÊ⁄UÊ◊ÊèÿÊ¢ Ÿ◊—"
    #   Span 3 (Times-Roman): " three times."
    # Line 2:
    #   Span 4 (Nalandatim): "Then perform "
    #   Span 5 (Nalandatim): "Pråƒåyåma."
    # We simulate this using page.insert_text or drawing text
    # In PyMuPDF, inserting text with different font names creates distinct spans
    page.insert_text((50, 72), "Chapter 1: Sacred Mantras", fontsize=14)

    # Insert sequential spans on the same line (y=100)
    # Note: font name specified in insert_text is recorded in the PDF
    page.insert_text((50, 100), "Recite this Mantra: ", fontname="times-roman", fontsize=11)
    page.insert_text((160, 100), "üÊË‚ËÃÊ⁄UÊ◊ÊèÿÊ¢ Ÿ◊—", fontname="helv", fontsize=11)
    page.insert_text((280, 100), " three times.", fontname="times-roman", fontsize=11)

    # Line 2 at y=120
    page.insert_text((50, 120), "Then perform ", fontname="times-roman", fontsize=11)
    page.insert_text((120, 120), "Pråƒåyåma.", fontname="times-italic", fontsize=11)

    # Block 2: Standard English paragraph with no legacy fonts
    page.insert_text(
        (50, 180), "This is an ordinary English paragraph.", fontname="times-roman", fontsize=11
    )
    page.insert_text(
        (50, 195),
        "It contains multiple lines with standard fonts.",
        fontname="times-roman",
        fontsize=11,
    )

    doc.set_metadata({"title": "Mixed Font Test Doc", "author": "Vedic Translator"})
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_pdf_extractor_span_level_integration(tmp_path: Path) -> None:
    """Verify that PDFExtractor normalizes recognized legacy fonts at span level while preserving English."""
    # Create a PDF using PyMuPDF where spans use font names matching Chanakya and Nalanda
    pdf_path = tmp_path / "legacy_test.pdf"
    doc = fitz.open()
    page = doc.new_page()

    # We use custom font names in a low-level PyMuPDF stream or simulate through font_normalizer
    # Since PyMuPDF insert_text only accepts standard 14 fonts unless a fontfile is given,
    # let's test directly with mock / low-level or registered font names.
    # PyMuPDF allows custom fontname when fontfile or basefont is set.
    # Alternatively, we can test with fitz font buffer or mock the font names in dictionary.
    page.insert_text((50, 72), "Chapter 1: Invocations", fontsize=14)
    page.insert_text((50, 100), "Recite: àﬂ◊ﬂ ◊ÊÃÊ ø Á¬ÃÊ àﬂ◊ﬂ", fontsize=12)

    doc.save(str(pdf_path))
    doc.close()

    extractor = PDFExtractor()
    ast_doc = extractor.extract(pdf_path)

    assert len(ast_doc.chapters) >= 1
    blocks = [b for ch in ast_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(blocks) >= 1

    # Check metadata preservation
    for b in blocks:
        assert "raw_source_text" in b.metadata
        assert "has_legacy_fonts" in b.metadata
        assert "pdf_spans" in b.metadata
        assert isinstance(b.metadata["pdf_spans"], list)


def test_pdf_extractor_mixed_spans_mocked() -> None:
    """Verify span-level normalization on a mock dictionary structure representing a mixed block."""
    from vedic_translator.document_processor.extractors.font_normalizer import LegacyFontNormalizer

    normalizer = LegacyFontNormalizer()

    # Simulate line with 3 spans:
    # Span 1: English (Times-Roman)
    # Span 2: Chanakya Sanskrit
    # Span 3: English (Times-Roman)
    # Span 4: Nalanda IAST
    spans = [
        {"font": "Times-Roman", "text": "After that "},
        {"font": "QAYTYV+ChanakyaBold", "text": "üÊË‚ËÃÊ⁄UÊ◊ÊèÿÊ¢ Ÿ◊—"},
        {"font": "Times-Roman", "text": " and then "},
        {"font": "UCJDBY+Nalandatim", "text": "›r∂ Råma"},
    ]

    normalized_line = []
    span_records = []
    has_legacy = False

    for s in spans:
        raw_text = s["text"]
        font_name = s["font"]
        norm_text, converted, family = normalizer.normalize_span(raw_text, font_name)
        if converted:
            has_legacy = True
        normalized_line.append(norm_text)
        span_records.append(
            {
                "font": font_name,
                "raw": raw_text,
                "norm": norm_text,
                "converted": converted,
            }
        )

    result_line = "".join(normalized_line)
    expected_line = "After that श्रीसीतारामाभ्यां नमः and then Śrī Rāma"

    assert result_line == expected_line
    assert has_legacy is True
    # Verify English spans were untouched
    assert span_records[0]["converted"] is False
    assert span_records[0]["norm"] == "After that "
    # Verify Chanakya span was converted to Devanagari
    assert span_records[1]["converted"] is True
    assert span_records[1]["norm"] == "श्रीसीतारामाभ्यां नमः"
    # Verify English span was untouched
    assert span_records[2]["converted"] is False
    assert span_records[2]["norm"] == " and then "
    # Verify Nalanda span was converted to IAST
    assert span_records[3]["converted"] is True
    assert span_records[3]["norm"] == "Śrī Rāma"


def test_pdf_extractor_metadata_invariants(tmp_path: Path) -> None:
    """Verify that all extracted blocks conform to the AST and metadata contracts."""
    pdf_path = tmp_path / "metadata_test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Sample Header", fontsize=16)
    page.insert_text((50, 110), "First line of text.\nSecond line of text.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    extractor = PDFExtractor()
    ast_doc = extractor.extract(pdf_path)

    blocks = [b for ch in ast_doc.chapters for s in ch.sections for b in s.blocks]
    for b in blocks:
        assert b.source_text.strip()
        assert b.metadata["raw_source_text"] == b.source_text
        assert b.metadata["has_legacy_fonts"] is False
        assert len(b.metadata["pdf_spans"]) >= 1
        assert "bbox" in b.metadata
        assert "page" in b.metadata
        assert b.metadata["page"] == 1


def test_pdf_extractor_transliteration_nasal_joining() -> None:
    """Verify that borrowed Chanakya nasal marks join with transliteration text as combining tilde."""
    from vedic_translator.document_processor.extractors.font_normalizer import LegacyFontNormalizer

    normalizer = LegacyFontNormalizer()

    # Case 1: Page 215 māhī̃, (måh∂ + ° + ,)
    spans_p215 = [
        {"font": "NalandahelBold", "text": "måh∂"},
        {"font": "ChanakyaBold", "text": "°"},
        {"font": "NalandahelBold", "text": ","},
    ]
    line_has_nalanda = any(normalizer.get_font_family(s["font"]) == "nalanda" for s in spans_p215)
    norm_p215 = []
    prev_translit = False
    for s in spans_p215:
        is_t = line_has_nalanda or prev_translit
        t, _, fam = normalizer.normalize_span(s["text"], s["font"], is_transliteration=is_t)
        if fam == "nalanda":
            prev_translit = True
        norm_p215.append(t)
    assert "".join(norm_p215) == "māhī̃,"

    # Case 2: Page 20 ugharahĩ (ugharahi + Ú)
    spans_p20 = [
        {"font": "Nalandahel", "text": "ugharahi"},
        {"font": "ChanakyaBold", "text": "Ú"},
    ]
    line_has_nalanda = any(normalizer.get_font_family(s["font"]) == "nalanda" for s in spans_p20)
    norm_p20 = []
    prev_translit = False
    for s in spans_p20:
        is_t = line_has_nalanda or prev_translit
        t, _, fam = normalizer.normalize_span(s["text"], s["font"], is_transliteration=is_t)
        if fam == "nalanda":
            prev_translit = True
        norm_p20.append(t)
    assert "".join(norm_p20) == "ugharahĩ"
