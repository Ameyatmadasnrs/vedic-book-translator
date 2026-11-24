"""Unit tests for local book reader server."""

import json
from pathlib import Path

from vedic_translator.direct_translation.reader_server import (
    BookReaderHandler,
    get_translation_stats,
)


def test_get_translation_stats(tmp_path: Path) -> None:
    """Verify calculation of contiguous translated page count."""
    translations_dir = tmp_path / "translations"
    translations_dir.mkdir()

    # Create dummy combined book file
    combined_file = translations_dir / "sri_ramcharitmanas_russian_edition.md"
    combined_file.write_text("# Book Title\n\nContent here...", encoding="utf-8")

    # Create dummy chunk files
    (translations_dir / "translation_pages_1_15.md").write_text("Chunk 1", encoding="utf-8")
    (translations_dir / "translation_pages_16_30.md").write_text("Chunk 2", encoding="utf-8")
    (translations_dir / "translation_pages_31_45.md").write_text("Chunk 3", encoding="utf-8")
    # Legacy chunk should be ignored
    (translations_dir / "translation_pages_215_229.md").write_text("Legacy", encoding="utf-8")

    stats = get_translation_stats(translations_dir)

    assert stats["total_source_pages"] == 1200
    assert stats["last_completed_page"] == 45
    assert stats["translated_pages_count"] == 45
    assert stats["percentage"] == 3.8
    assert stats["chunks_count"] == 3
    assert stats["file_size"] > 0


def test_reader_handler_endpoints(tmp_path: Path) -> None:
    """Verify handler responds to GET /, /status.json, /sri_ramcharitmanas_russian_edition.md, and legacy /api/*."""
    from unittest.mock import MagicMock

    translations_dir = tmp_path / "translations"
    translations_dir.mkdir()
    combined_file = translations_dir / "sri_ramcharitmanas_russian_edition.md"
    combined_file.write_text("# Chapter 1\n\nPoetic text", encoding="utf-8")
    (translations_dir / "translation_pages_1_15.md").write_text("Chunk 1", encoding="utf-8")

    # Mock handler request
    handler = BookReaderHandler.__new__(BookReaderHandler)
    handler.translations_dir = translations_dir
    handler.wfile = MagicMock()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    # Test GET /
    handler.path = "/"
    handler.do_GET()
    handler.send_response.assert_called_with(200)

    # Test GET /status.json with query parameter
    handler.send_response.reset_mock()
    handler.wfile.reset_mock()
    handler.path = "/status.json?_t=1700000000"
    handler.do_GET()
    handler.send_response.assert_called_with(200)
    written_status = b"".join(call.args[0] for call in handler.wfile.write.call_args_list)
    status_json = json.loads(written_status.decode("utf-8"))
    assert status_json["last_completed_page"] == 15

    # Test GET /sri_ramcharitmanas_russian_edition.md with query parameter
    handler.send_response.reset_mock()
    handler.wfile.reset_mock()
    handler.path = "/sri_ramcharitmanas_russian_edition.md?_t=1700000000"
    handler.do_GET()
    handler.send_response.assert_called_with(200)
    written_md = b"".join(call.args[0] for call in handler.wfile.write.call_args_list)
    assert "# Chapter 1" in written_md.decode("utf-8")

    # Test legacy GET /api/status
    handler.send_response.reset_mock()
    handler.wfile.reset_mock()
    handler.path = "/api/status"
    handler.do_GET()
    handler.send_response.assert_called_with(200)
    written = b"".join(call.args[0] for call in handler.wfile.write.call_args_list)
    status_data = json.loads(written.decode("utf-8"))
    assert status_data["last_completed_page"] == 15

    # Test legacy GET /api/book
    handler.send_response.reset_mock()
    handler.wfile.reset_mock()
    handler.path = "/api/book"
    handler.do_GET()
    handler.send_response.assert_called_with(200)
    written_book = b"".join(call.args[0] for call in handler.wfile.write.call_args_list)
    book_data = json.loads(written_book.decode("utf-8"))
    assert "# Chapter 1" in book_data["markdown"]

    # Test 404
    handler.send_response.reset_mock()
    handler.path = "/nonexistent"
    handler.do_GET()
    handler.send_response.assert_called_with(404)


def test_reader_html_static_compatibility() -> None:
    """Verify READER_HTML uses relative static files and handles errors gracefully."""
    from vedic_translator.direct_translation.reader_server import READER_HTML

    # Must use relative paths for GitHub Pages compatibility
    assert "./status.json" in READER_HTML
    assert "./sri_ramcharitmanas_russian_edition.md" in READER_HTML

    # Must NOT rely on server-only /api/ endpoints
    assert "fetch('/api/book')" not in READER_HTML
    assert "fetch('/api/status')" not in READER_HTML

    # Must read markdown via .text() and parse it
    assert ".text()" in READER_HTML
    assert "parseMarkdown" in READER_HTML

    # Must include Russian error handling message and retry button
    assert "Не удалось загрузить книгу" in READER_HTML
    assert "Повторить попытку" in READER_HTML
