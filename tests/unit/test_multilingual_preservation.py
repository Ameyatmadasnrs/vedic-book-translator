"""Unit tests verifying general-purpose multilingual text preservation across all extractors.

Validates that digital extraction does not assume Sanskrit-only and preserves:
1. Pure English literary prose
2. Russian Cyrillic text
3. Sanskrit in Devanagari script
4. Sanskrit transliteration with Latin diacritics (IAST)
5. Mixed-language multilingual paragraphs
"""

from pathlib import Path

import pymupdf as fitz
from docx import Document as CreateDocx
from ebooklib import epub

from vedic_translator.document_processor.extractors import (
    DOCXExtractor,
    EPUBExtractor,
    PDFExtractor,
    TXTExtractor,
)

# Test content covering all required linguistic targets
ENGLISH_PROSE = (
    "Philosophy is not a theoretical speculation, but a practical way of living. "
    "The journey of self-realization begins with inquiry into the nature of consciousness."
)

RUSSIAN_CYRILLIC = (
    "Введение в ведическую философию. "
    "Истинное знание раскрывает вечную природу живого существа и его взаимоотношения с Абсолютом. "
    "Каждый ищущий истину должен стремиться к глубокому пониманию бытия."
)

SANSKRIT_DEVANAGARI = (
    "ॐ असतो मा सद्गमय । तमसो मा ज्योतिर्गमय । मृत्योर्मा अमृतं गमय ॥ सर्वे भवन्तु सुखिनः सर्वे सन्तु निरामयाः ।"
)

SANSKRIT_IAST_DIACRITICS = (
    "oṁ pūrṇam adaḥ pūrṇam idaṁ pūrṇāt pūrṇam udacyate | "
    "ṛṣiḥ, kṛṣṇaḥ, caitanyaḥ, śrīla, bhagavān, ānandaḥ, viṣṇuḥ, jñānam, "
    "saṁsāra, mādhurya, vaiṣṇava, ātmā, prakṛtiḥ, guṇāḥ, muktiḥ."
)

MIXED_MULTILINGUAL_PARAGRAPH = (
    "The sage (ṛṣiḥ) addressed the king: «Истинное благо — это духовное пробуждение». "
    "He recited the ancient mantra: ॐ तत्सत् (oṁ tat sat), emphasizing that jñāna and bhakti "
    "must harmonize in one's life. Это путь вечной гармонии (śāntiḥ)."
)


def test_txt_multilingual_preservation(tmp_path: Path) -> None:
    """Verify TXTExtractor preserves English, Russian, Sanskrit, and mixed multilingual text."""
    txt_file = tmp_path / "multilingual.txt"
    full_content = (
        f"# Chapter 1: English Literature\n\n{ENGLISH_PROSE}\n\n"
        f"# Chapter 2: Русская Литература\n\n{RUSSIAN_CYRILLIC}\n\n"
        f"# Chapter 3: संस्कृत-साहित्यम्\n\n{SANSKRIT_DEVANAGARI}\n\n"
        f"# Chapter 4: IAST Romanization\n\n{SANSKRIT_IAST_DIACRITICS}\n\n"
        f"# Chapter 5: Mixed Discourse\n\n{MIXED_MULTILINGUAL_PARAGRAPH}\n"
    )
    txt_file.write_text(full_content, encoding="utf-8")

    extractor = TXTExtractor()
    doc = extractor.extract(txt_file)

    assert len(doc.chapters) == 5
    all_extracted_text = " ".join(
        b.source_text for ch in doc.chapters for s in ch.sections for b in s.blocks
    )

    # 1. English
    assert ENGLISH_PROSE in all_extracted_text
    # 2. Russian
    assert RUSSIAN_CYRILLIC in all_extracted_text
    # 3. Sanskrit Devanagari
    assert "ॐ असतो मा सद्गमय" in all_extracted_text
    assert "सर्वे भवन्तु सुखिनः" in all_extracted_text
    # 4. Sanskrit IAST with diacritics
    assert "oṁ pūrṇam adaḥ" in all_extracted_text
    assert "ṛṣiḥ" in all_extracted_text
    assert "saṁsāra" in all_extracted_text
    assert "vaiṣṇava" in all_extracted_text
    # 5. Mixed-language paragraph
    assert "The sage (ṛṣiḥ) addressed the king" in all_extracted_text
    assert "«Истинное благо — это духовное пробуждение»" in all_extracted_text
    assert "ॐ तत्सत्" in all_extracted_text


def test_docx_multilingual_preservation(tmp_path: Path) -> None:
    """Verify DOCXExtractor preserves English, Russian, Sanskrit, and mixed multilingual text."""
    docx_file = tmp_path / "multilingual.docx"
    doc_builder = CreateDocx()
    doc_builder.core_properties.title = "Multilingual Anthology"

    doc_builder.add_heading("Section 1: English Prose", level=1)
    doc_builder.add_paragraph(ENGLISH_PROSE)

    doc_builder.add_heading("Section 2: Русский Текст", level=1)
    doc_builder.add_paragraph(RUSSIAN_CYRILLIC)

    doc_builder.add_heading("Section 3: देवनागरी", level=1)
    doc_builder.add_paragraph(SANSKRIT_DEVANAGARI)

    doc_builder.add_heading("Section 4: IAST Diacritics", level=1)
    doc_builder.add_paragraph(SANSKRIT_IAST_DIACRITICS)

    doc_builder.add_heading("Section 5: Mixed Multilingual", level=1)
    doc_builder.add_paragraph(MIXED_MULTILINGUAL_PARAGRAPH)

    doc_builder.save(str(docx_file))

    extractor = DOCXExtractor()
    doc = extractor.extract(docx_file)

    assert doc.metadata.title == "Multilingual Anthology"
    all_extracted_text = " ".join(
        b.source_text for ch in doc.chapters for s in ch.sections for b in s.blocks
    )

    assert ENGLISH_PROSE in all_extracted_text
    assert RUSSIAN_CYRILLIC in all_extracted_text
    assert "ॐ असतो मा सद्गमय" in all_extracted_text
    assert "vaiṣṇava" in all_extracted_text
    assert "Истинное благо" in all_extracted_text


def test_epub_multilingual_preservation(tmp_path: Path) -> None:
    """Verify EPUBExtractor preserves English, Russian, Sanskrit, and mixed multilingual text."""
    epub_file = tmp_path / "multilingual.epub"
    book = epub.EpubBook()
    book.set_identifier("multi-lang-99")
    book.set_title("Multilingual Reader")
    book.set_language("en")

    chapter = epub.EpubHtml(title="Multilingual Chapter", file_name="multi.xhtml", lang="en")
    chapter.content = (
        "<html><body>"
        "<h1>Multilingual Chapter</h1>"
        f"<p>{ENGLISH_PROSE}</p>"
        f"<p>{RUSSIAN_CYRILLIC}</p>"
        f"<p>{SANSKRIT_DEVANAGARI}</p>"
        f"<p>{SANSKRIT_IAST_DIACRITICS}</p>"
        f"<p>{MIXED_MULTILINGUAL_PARAGRAPH}</p>"
        "</body></html>"
    )
    book.add_item(chapter)
    book.toc = (chapter,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    doc = extractor.extract(epub_file)

    assert doc.metadata.title == "Multilingual Reader"
    all_extracted_text = " ".join(
        b.source_text for ch in doc.chapters for s in ch.sections for b in s.blocks
    )

    assert "theoretical speculation" in all_extracted_text
    assert "Введение в ведическую философию" in all_extracted_text
    assert "मृत्योर्मा अमृतं गमय" in all_extracted_text
    assert "caitanyaḥ" in all_extracted_text
    assert "The sage (ṛṣiḥ)" in all_extracted_text


def test_pdf_multilingual_preservation(tmp_path: Path) -> None:
    """Verify PDFExtractor preserves English, Russian, and IAST text."""
    pdf_file = tmp_path / "multilingual.pdf"
    doc_pdf = fitz.open()

    arial_font = "C:/Windows/Fonts/arial.ttf"
    nirmala_font = "C:/Windows/Fonts/Nirmala.ttc"
    has_arial = Path(arial_font).exists()
    has_nirmala = Path(nirmala_font).exists()

    page = doc_pdf.new_page()
    if has_arial:
        page.insert_font(fontname="arial", fontfile=arial_font)
        page.insert_text(
            (50, 70), "Chapter 1: Multilingual Overview", fontname="arial", fontsize=14
        )
        page.insert_text((50, 100), ENGLISH_PROSE[:100], fontname="arial", fontsize=11)
        page.insert_text(
            (50, 140), "Русский текст: глубокое понимание бытия.", fontname="arial", fontsize=11
        )
        page.insert_text(
            (50, 180),
            "IAST: oṁ pūrṇam adaḥ pūrṇam idaṁ, vaiṣṇava, kṛṣṇa.",
            fontname="arial",
            fontsize=11,
        )
    else:
        page.insert_text((50, 70), "Chapter 1: Multilingual Overview", fontsize=14)
        page.insert_text((50, 100), ENGLISH_PROSE[:100], fontsize=11)

    if has_nirmala:
        page.insert_font(fontname="nirmala", fontfile=nirmala_font)
        page.insert_text((50, 220), "ॐ असतो मा सद्गमय ।", fontname="nirmala", fontsize=12)

    doc_pdf.save(str(pdf_file))
    doc_pdf.close()

    extractor = PDFExtractor()
    doc = extractor.extract(pdf_file)

    all_source_text = " ".join(
        b.source_text for ch in doc.chapters for s in ch.sections for b in s.blocks
    )
    all_normalized_text = " ".join(
        b.normalized_text for ch in doc.chapters for s in ch.sections for b in s.blocks
    )

    # 1. Normalized text has ordinary spaces for downstream search/tokenization
    assert "Multilingual Overview" in all_normalized_text
    assert "theoretical speculation" in all_normalized_text
    assert "\xa0" not in all_normalized_text

    # 2. Source text preserves raw characters (including \xa0 when emitted by font/PDF)
    if has_arial:
        assert "\xa0" in all_source_text
        assert "глубокое понимание" in all_normalized_text
        assert "oṁ pūrṇam adaḥ" in all_normalized_text
    if has_nirmala:
        assert "ॐ असतो मा" in all_normalized_text
