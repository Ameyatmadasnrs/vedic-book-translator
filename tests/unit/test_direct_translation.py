"""Unit tests for Direct PDF Translation MVP."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest

from vedic_translator.direct_translation.cli import parse_args
from vedic_translator.direct_translation.translator import (
    split_pdf_chunk,
    translate_pdf_chunk,
)


def test_cli_parse_args_custom_values() -> None:
    """Test that CLI argument parsing correctly binds all user-specified flags."""
    args = parse_args(
        [
            "--pdf-path",
            "dummy.pdf",
            "--start-page",
            "100",
            "--num-pages",
            "20",
            "--model",
            "gemini-3.5-flash-lite",
            "--temperature",
            "0.3",
        ]
    )
    assert args.pdf_path == "dummy.pdf"
    assert args.start_page == 100
    assert args.num_pages == 20
    assert args.model == "gemini-3.5-flash-lite"
    assert args.temperature == 0.3


def test_split_pdf_chunk_valid_range(tmp_path: Path) -> None:
    """Test splitting a real PDF into an exact page chunk."""
    src_pdf = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not src_pdf.exists():
        pytest.skip("Test book PDF not available in workspace")

    chunk_dir = tmp_path / "chunks"
    chunk_path, start, end = split_pdf_chunk(
        source_pdf_path=src_pdf,
        start_page=215,
        num_pages=3,
        output_dir=chunk_dir,
    )

    assert start == 215
    assert end == 217
    assert chunk_path.exists()
    assert chunk_path.name == "chunk_pages_215_217.pdf"

    # Verify that the generated sub-PDF has exactly 3 pages
    doc = pymupdf.open(chunk_path)
    assert doc.page_count == 3
    doc.close()


def test_split_pdf_chunk_invalid_parameters(tmp_path: Path) -> None:
    """Test that split_pdf_chunk validates input page ranges."""
    src_pdf = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not src_pdf.exists():
        pytest.skip("Test book PDF not available in workspace")

    chunk_dir = tmp_path / "chunks"

    with pytest.raises(ValueError, match="start_page must be >= 1"):
        split_pdf_chunk(src_pdf, start_page=0, num_pages=5, output_dir=chunk_dir)

    with pytest.raises(ValueError, match="num_pages must be >= 1"):
        split_pdf_chunk(src_pdf, start_page=1, num_pages=0, output_dir=chunk_dir)

    with pytest.raises(ValueError, match="exceeds total pages"):
        split_pdf_chunk(src_pdf, start_page=99999, num_pages=5, output_dir=chunk_dir)

    with pytest.raises(FileNotFoundError):
        split_pdf_chunk(Path("non_existent.pdf"), start_page=1, num_pages=5, output_dir=chunk_dir)


def test_translate_pdf_chunk_mock_workflow(tmp_path: Path) -> None:
    """Test translate_pdf_chunk upload, generation, and cleanup with mocked Gemini client."""
    chunk_pdf = tmp_path / "chunk_pages_215_229.pdf"
    chunk_pdf.write_bytes(b"%PDF-1.4 mock pdf content")

    master_prompt = tmp_path / "master_system_prompt.txt"
    master_prompt.write_text("Master system instructions", encoding="utf-8")

    working_prompt = tmp_path / "working_fragment_prompt.txt"
    working_prompt.write_text("Working fragment instructions", encoding="utf-8")

    output_dir = tmp_path / "translations"

    mock_client = MagicMock()
    mock_file = MagicMock()
    mock_file.name = "files/mock123"
    mock_client.files.upload.return_value = mock_file

    mock_response = MagicMock()
    mock_response.text = "# Тестовый русский перевод\n\nСтих 1..."
    mock_response.usage_metadata.prompt_token_count = 1500
    mock_response.usage_metadata.candidates_token_count = 800
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("vedic_translator.direct_translation.translator.resolve_api_key", return_value="dummy_key"),
    ):
        result = translate_pdf_chunk(
            chunk_pdf_path=chunk_pdf,
            master_prompt_path=master_prompt,
            working_prompt_path=working_prompt,
            output_dir=output_dir,
            model_name="gemini-3.5-flash-lite",
            project_root=tmp_path,
        )

    # 1. Verify upload called with chunk path
    mock_client.files.upload.assert_called_once_with(file=str(chunk_pdf))

    # 2. Verify generation called with uploaded file and working prompt
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.5-flash-lite"
    assert call_kwargs["contents"][0] == mock_file
    assert call_kwargs["contents"][1] == "Working fragment instructions"
    assert call_kwargs["config"].system_instruction == "Master system instructions"

    # 3. Verify remote file was deleted after generation
    mock_client.files.delete.assert_called_once_with(name="files/mock123")

    # 4. Verify output file created and structured
    assert result.output_markdown_path.exists()
    assert result.output_markdown_path.name == "translation_pages_215_229.md"
    content = result.output_markdown_path.read_text(encoding="utf-8")
    assert "Страницы 215–229" in content
    assert "gemini-3.5-flash-lite" in content
    assert "# Тестовый русский перевод" in content
    assert result.input_tokens == 1500
    assert result.output_tokens == 800
