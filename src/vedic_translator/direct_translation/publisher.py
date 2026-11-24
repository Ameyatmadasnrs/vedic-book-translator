"""Web publisher for Sri Ramcharitmanas Russian Edition.

Synchronizes the continuous translation edition and progress metadata to docs/
for seamless public web hosting via GitHub Pages, with automatic git push.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from vedic_translator.direct_translation.reader_server import (
    READER_HTML,
    get_translation_stats,
)


def sync_web_reader(project_root: Path | None = None) -> dict[str, Any]:
    """Synchronize the accumulated book edition and status into docs/ for web hosting.

    Args:
        project_root: Root directory of the repository.

    Returns:
        Dict with updated progress statistics.
    """
    root = project_root or Path.cwd()
    translations_dir = root / "data" / "direct_translation" / "translations"
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    src_book = translations_dir / "sri_ramcharitmanas_russian_edition.md"
    dst_book = docs_dir / "sri_ramcharitmanas_russian_edition.md"

    if src_book.exists():
        shutil.copy2(src_book, dst_book)
        logger.info(f"Copied {src_book.name} -> {dst_book} ({dst_book.stat().st_size} bytes)")
    else:
        logger.warning(f"Source book {src_book} does not exist yet.")

    # 1. Generate status metadata
    stats = get_translation_stats(translations_dir)
    status_file = docs_dir / "status.json"
    status_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Updated {status_file.name} (pages: {stats['last_completed_page']}/{stats['total_source_pages']})")

    # 2. Write index.html (self-contained reader supporting GitHub Pages & static hosting)
    index_file = docs_dir / "index.html"
    index_file.write_text(READER_HTML, encoding="utf-8")
    logger.info(f"Updated web reader at: {index_file}")

    return stats


def publish_to_github(
    commit_message: str,
    project_root: Path | None = None,
    push: bool = True,
) -> bool:
    """Stage published files, create git commit, and push to remote origin main.

    Args:
        commit_message: Descriptive git commit message.
        project_root: Root directory of the repository.
        push: Whether to execute git push.

    Returns:
        True if commit and push succeeded, False otherwise.
    """
    root = project_root or Path.cwd()

    try:
        # 1. Sync docs/ first
        sync_web_reader(root)

        # 2. Add docs, translations, prompts, code, and tests (excluding .env, data/test_books, input_chunks)
        files_to_stage = [
            "docs",
            ".github",
            ".gitignore",
            "data/direct_translation/prompts",
            "data/direct_translation/translations",
            "src",
            "tests",
        ]

        logger.info("Staging files for commit...")
        subprocess.run(
            ["git", "add", *files_to_stage],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        # 3. Check if there are changes to commit
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        if not status_res.stdout.strip():
            logger.info("No changes to commit. Working tree clean.")
            return True

        # 4. Commit
        logger.info(f"Creating commit: {commit_message}")
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        # 5. Push
        if push:
            logger.info("Pushing to origin main...")
            push_res = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Pushed to GitHub successfully: {push_res.stdout.strip()}")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e.cmd} - stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Failed to publish to GitHub: {e}")
        return False


if __name__ == "__main__":
    stats = sync_web_reader()
    print(f"Web reader synced to docs/ (Last page: {stats['last_completed_page']})")
