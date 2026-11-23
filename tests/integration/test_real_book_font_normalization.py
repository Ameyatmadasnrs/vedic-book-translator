"""Integration tests for legacy font normalization on the real Ramcharita Manas test book."""

from pathlib import Path

import pytest

from vedic_translator.document_processor.extractors.pdf import PDFExtractor

REAL_BOOK_PATH = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")


@pytest.fixture(scope="module")
def extracted_doc():
    """Extract document once for module-level integration assertions."""
    extractor = PDFExtractor()
    return extractor.extract(REAL_BOOK_PATH)


@pytest.mark.skipif(
    not REAL_BOOK_PATH.exists(), reason="Test book PDF not found in data/test_books/"
)
class TestRealBookFontNormalization:
    """Integration test suite executing against Ramcharita_Manas_Gita_Press.pdf."""

    def test_total_blocks_extracted(self, extracted_doc) -> None:
        """Verify 1200-page extraction yields non-empty chapters and thousands of blocks."""
        assert len(extracted_doc.chapters) >= 1
        total_b = extracted_doc.total_blocks()
        assert total_b > 10000

    def test_page_2_sanskrit_prayer(self, extracted_doc) -> None:
        """Verify that Page 2 Sanskrit prayer is normalized to clean Unicode Devanagari."""
        page_2_blocks = [
            b
            for ch in extracted_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") == 2
        ]
        assert len(page_2_blocks) >= 1
        page_2_text = " ".join(" ".join(b.source_text.split()) for b in page_2_blocks)

        assert "त्वमेव माता च पिता त्वमेव" in page_2_text
        assert "त्वमेव बन्धुश्च सखा त्वमेव" in page_2_text
        assert "त्वमेव विद्या द्रविणं त्वमेव" in page_2_text
        assert "त्वमेव सर्व मम देवदेव" in page_2_text

    def test_page_12_mixed_mantra_block(self, extracted_doc) -> None:
        """Verify Page 12 Block 13 maintains English untouched while normalizing Sanskrit and IAST."""
        page_12_blocks = [
            b
            for ch in extracted_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") == 12
        ]
        target_block = None
        for b in page_12_blocks:
            if "recitation of the following Mantras" in b.source_text:
                target_block = b
                break

        assert target_block is not None
        # Verify Sanskrit mantras were normalized
        assert "श्रीसीतारामाभ्यां नमः" in target_block.source_text
        assert "श्रीरामभद्राय नमः" in target_block.source_text
        # Verify English text was preserved untouched
        assert "Then water should be sipped thrice with the recitation" in target_block.source_text
        assert "after another " in target_block.source_text
        # Verify IAST transliteration was normalized
        assert "Prāṇāyāma should also be" in target_block.source_text
        assert "sacred to Sītā and Śrī Rāma" in target_block.source_text
        # Verify metadata
        assert target_block.metadata["has_legacy_fonts"] is True
        assert len(target_block.metadata["pdf_spans"]) >= 5

    def test_page_215_doha_and_chaupai(self, extracted_doc) -> None:
        """Verify Page 215 Doha 188 is converted to Unicode Devanagari."""
        page_215_blocks = [
            b
            for ch in extracted_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") == 215
        ]
        p215_text = " ".join(b.source_text for b in page_215_blocks)
        assert "कौसल्यादि नारि प्रिय सब आचरन पुनीत" in p215_text
        assert "पति अनुकूल प्रेम दृढ़ हरि पद कमल बिनीत" in p215_text
