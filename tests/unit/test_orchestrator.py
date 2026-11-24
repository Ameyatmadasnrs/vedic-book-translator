"""Unit tests for direct translation orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vedic_translator.direct_translation.orchestrator import (
    append_chunk_to_edition,
    run_pipeline_chunk,
)


def test_append_chunk_to_edition(tmp_path: Path) -> None:
    """Verify stripping of metadata header and appending to continuous edition."""
    book_file = tmp_path / "book.md"
    book_file.write_text("# Initial Content\n\nChapter 1 line.", encoding="utf-8")

    chunk_file = tmp_path / "chunk.md"
    chunk_file.write_text(
        "# Header\n"
        "**Info:** Data\n"
        "---\n\n"
        "# БАЛА-КАНДА («Книга о детстве»)\n\n"
        "This is the actual narrative text.\n",
        encoding="utf-8",
    )

    chars = append_chunk_to_edition(chunk_file, book_file)
    assert chars > 0

    content = book_file.read_text(encoding="utf-8")
    assert "# Initial Content" in content
    assert "This is the actual narrative text." in content
    # The header metadata and redundant # БАЛА-КАНДА should be stripped
    assert "**Info:** Data" not in content
    assert content.count("# БАЛА-КАНДА") == 0


@patch("vedic_translator.direct_translation.orchestrator.publish_to_github")
@patch("vedic_translator.direct_translation.orchestrator.sync_web_reader")
@patch("vedic_translator.direct_translation.orchestrator.translate_pdf_chunk")
@patch("vedic_translator.direct_translation.orchestrator.split_pdf_chunk")
def test_run_pipeline_chunk(
    mock_split,
    mock_translate,
    mock_sync,
    mock_publish,
    tmp_path: Path,
) -> None:
    """Verify orchestrator workflow from splitting to publishing."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    prompts_dir = tmp_path / "data" / "direct_translation" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "master_system_prompt.txt").write_text("Master", encoding="utf-8")
    (prompts_dir / "working_fragment_prompt.txt").write_text("Fragment", encoding="utf-8")

    chunk_pdf = tmp_path / "chunk_121_135.pdf"
    chunk_pdf.write_bytes(b"%PDF-1.4 chunk")
    mock_split.return_value = (chunk_pdf, 121, 135)

    mock_res = MagicMock()
    mock_res.output_markdown_path = tmp_path / "out.md"
    mock_res.translation_text = "---\n\nTranslated story content here."
    mock_res.duration_seconds = 12.5
    (tmp_path / "out.md").write_text(mock_res.translation_text, encoding="utf-8")
    mock_translate.return_value = mock_res

    mock_sync.return_value = {
        "last_completed_page": 135,
        "percentage": 11.2,
    }
    mock_publish.return_value = True

    summary = run_pipeline_chunk(
        start_page=121,
        num_pages=15,
        pdf_path=pdf_path,
        auto_publish=True,
        project_root=tmp_path,
    )

    assert summary["start_page"] == 121
    assert summary["end_page"] == 135
    assert summary["last_completed_page"] == 135
    assert summary["published_to_github"] is True
    assert mock_split.called
    assert mock_translate.called
    assert mock_sync.called
    assert mock_publish.called
