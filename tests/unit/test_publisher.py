"""Unit tests for web publisher module."""

import json
from pathlib import Path
from unittest.mock import patch

from vedic_translator.direct_translation.publisher import (
    publish_to_github,
    sync_web_reader,
)


def test_sync_web_reader(tmp_path: Path) -> None:
    """Verify synchronization of book edition and status to docs/."""
    # Setup mock project structure
    translations_dir = tmp_path / "data" / "direct_translation" / "translations"
    translations_dir.mkdir(parents=True)
    book_file = translations_dir / "sri_ramcharitmanas_russian_edition.md"
    book_file.write_text("# Book Title\n\nRussian content here...", encoding="utf-8")
    (translations_dir / "translation_pages_1_15.md").write_text("Chunk 1", encoding="utf-8")

    stats = sync_web_reader(project_root=tmp_path)

    docs_dir = tmp_path / "docs"
    assert (docs_dir / "sri_ramcharitmanas_russian_edition.md").exists()
    assert (docs_dir / "status.json").exists()
    assert (docs_dir / "index.html").exists()

    status_data = json.loads((docs_dir / "status.json").read_text(encoding="utf-8"))
    assert status_data["last_completed_page"] == 15
    assert stats["last_completed_page"] == 15


@patch("subprocess.run")
def test_publish_to_github(mock_run, tmp_path: Path) -> None:
    """Verify git staging, commit, and push execution."""
    translations_dir = tmp_path / "data" / "direct_translation" / "translations"
    translations_dir.mkdir(parents=True)
    (translations_dir / "sri_ramcharitmanas_russian_edition.md").write_text("# Title", encoding="utf-8")

    mock_run.return_value.stdout = " M docs/index.html\n"

    success = publish_to_github(
        commit_message="docs: update reader",
        project_root=tmp_path,
        push=True,
    )

    assert success is True
    assert mock_run.call_count >= 3
