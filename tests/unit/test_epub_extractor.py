"""Unit tests for EPUBExtractor."""

from pathlib import Path

import pytest
from ebooklib import epub

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    UnsupportedFormatError,
)
from vedic_translator.document_processor.extractors.epub import EPUBExtractor


def test_epub_extractor_supports() -> None:
    extractor = EPUBExtractor()
    assert extractor.supports(Path("test.epub"))
    assert not extractor.supports(Path("test.docx"))


def test_epub_extractor_valid_book(tmp_path: Path) -> None:
    epub_file = tmp_path / "vedic_book.epub"
    book = epub.EpubBook()
    book.set_identifier("vedic-12345")
    book.set_title("Sri Isopanisad")
    book.set_language("en")
    book.add_author("A.C. Bhaktivedanta Swami Prabhupada")

    # Chapter 1
    c1 = epub.EpubHtml(title="Invocation", file_name="invoc.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<h1>Invocation</h1>"
        "<p>ॐ पूर्णमदः पूर्णमिदं पूर्णात्पूर्णमुदच्यते ।</p>"
        "<p>oṁ pūrṇam adaḥ pūrṇam idaṁ pūrṇāt pūrṇam udacyate</p>"
        "<p>Верховный Господь совершенен и полон...</p>"
        "</body></html>"
    )
    book.add_item(c1)

    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    ast_doc = extractor.extract(epub_file)

    assert ast_doc.metadata.title == "Sri Isopanisad"
    assert ast_doc.metadata.author == "A.C. Bhaktivedanta Swami Prabhupada"
    assert len(ast_doc.chapters) >= 1

    ch = ast_doc.chapters[0]
    assert ch.title == "Invocation"

    all_text = " ".join(b.source_text for s in ch.sections for b in s.blocks)
    assert "ॐ पूर्णमदः" in all_text
    assert "pūrṇam adaḥ" in all_text
    assert "Верховный Господь" in all_text


def test_epub_extractor_corrupted_file(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.epub"
    corrupt_file.write_bytes(b"Not an epub file")

    extractor = EPUBExtractor()
    with pytest.raises(CorruptedDocumentError):
        extractor.extract(corrupt_file)


def test_epub_extractor_unsupported_format(tmp_path: Path) -> None:
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("dummy", encoding="utf-8")

    extractor = EPUBExtractor()
    with pytest.raises(UnsupportedFormatError):
        extractor.extract(txt_file)
