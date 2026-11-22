"""Unit tests for TXTExtractor."""

from pathlib import Path

import pytest

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    UnsupportedFormatError,
)
from vedic_translator.document_processor.extractors.txt import TXTExtractor


def test_txt_extractor_supports() -> None:
    extractor = TXTExtractor()
    assert extractor.supports(Path("test.txt"))
    assert extractor.supports(Path("test.md"))
    assert extractor.supports(Path("test.TEXT"))
    assert not extractor.supports(Path("test.pdf"))


def test_txt_extractor_sanskrit_unicode(tmp_path: Path) -> None:
    sample_file = tmp_path / "gita_sample.txt"
    content = (
        "# Chapter 1: Observing the Armies\n\n"
        "## Text 1\n\n"
        "धृतराष्ट्र उवाच\n"
        "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।\n"
        "मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १ ॥\n\n"
        "dhṛtarāṣṭra uvāca\n"
        "dharma-kṣetre kuru-kṣetre samavetā yuyutsavaḥ\n"
        "māmakāḥ pāṇḍavāś caiva kim akurvata sañjaya\n\n"
        "Дхритараштра сказал: О Санджая, что сделали мои сыновья и сыновья Панду...\n"
    )
    sample_file.write_text(content, encoding="utf-8")

    extractor = TXTExtractor()
    doc = extractor.extract(sample_file)

    assert doc.metadata.title == "Chapter 1: Observing the Armies"
    assert len(doc.chapters) == 1
    chapter = doc.chapters[0]
    assert chapter.chapter_index == 1
    assert "Chapter 1" in chapter.title

    # Verify Unicode preserved exactly
    all_text = " ".join(b.source_text for s in chapter.sections for b in s.blocks)
    assert "धर्मक्षेत्रे कुरुक्षेत्रे" in all_text
    assert "dharma-kṣetre kuru-kṣetre" in all_text
    assert "Дхритараштра сказал" in all_text


def test_txt_extractor_empty_file_fails(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    extractor = TXTExtractor()
    with pytest.raises(CorruptedDocumentError):
        extractor.extract(empty_file)


def test_txt_extractor_unsupported_format(tmp_path: Path) -> None:
    dummy_file = tmp_path / "test.xyz"
    dummy_file.write_text("hello", encoding="utf-8")

    extractor = TXTExtractor()
    with pytest.raises(UnsupportedFormatError):
        extractor.extract(dummy_file)
