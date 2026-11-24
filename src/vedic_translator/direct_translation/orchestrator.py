"""Orchestrator for automated direct PDF translation, book edition compilation, and GitHub sync.

Provides end-to-end automated pipeline:
1. Splits target page ranges into PDF fragments.
2. Translates fragment via multimodal Gemini API into literary Russian.
3. Automatically strips metadata headers and appends to the unified Russian edition.
4. Synchronizes web reader assets and metadata to docs/.
5. Publishes and pushes updates to GitHub Pages remote repository.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from vedic_translator.direct_translation.publisher import (
    publish_to_github,
    sync_web_reader,
)
from vedic_translator.direct_translation.translator import (
    split_pdf_chunk,
    translate_pdf_chunk,
)

DEFAULT_PDF_PATH = Path(
    r"C:\Users\Ameya\Desktop\Amar\Рамаяна\Ramcharita Manas (Hindi & English Translation) Gita Press.pdf"
)
FALLBACK_PDF_PATH = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")


def append_chunk_to_edition(
    chunk_markdown_path: Path,
    book_markdown_path: Path,
) -> int:
    """Clean chunk header and append translated body to the unified edition.

    Args:
        chunk_markdown_path: Path to the generated chunk markdown file.
        book_markdown_path: Path to the unified Russian edition markdown file.

    Returns:
        Number of characters appended.
    """
    raw_text = chunk_markdown_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    body_lines: list[str] = []
    skip_header = True
    for line in lines:
        if skip_header:
            if line.strip().startswith("---"):
                skip_header = False
            continue
        # Avoid repeating root book/kanda titles that are already in the unified header
        if line.strip().startswith("# БАЛА-КАНДА"):
            continue
        body_lines.append(line)

    cleaned_body = "\n".join(body_lines).strip()
    if not cleaned_body:
        logger.warning(f"No body content found in {chunk_markdown_path} after cleaning.")
        return 0

    if book_markdown_path.exists():
        existing_book = book_markdown_path.read_text(encoding="utf-8").rstrip()
        updated_book = existing_book + "\n\n" + cleaned_body + "\n"
    else:
        book_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        updated_book = cleaned_body + "\n"

    book_markdown_path.write_text(updated_book, encoding="utf-8")
    logger.info(
        f"Appended {len(cleaned_body)} chars from {chunk_markdown_path.name} to {book_markdown_path.name}"
    )
    return len(cleaned_body)


def run_pipeline_chunk(
    start_page: int,
    num_pages: int = 15,
    pdf_path: Path | None = None,
    model_name: str = "gemini-3.5-flash-lite",
    auto_publish: bool = True,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Execute complete direct translation pipeline for a single chunk.

    Args:
        start_page: Starting page number in the source PDF.
        num_pages: Number of pages in chunk.
        pdf_path: Path to source PDF.
        model_name: Gemini model name.
        auto_publish: Whether to commit and push changes to GitHub.
        project_root: Repository root directory.

    Returns:
        Dict with execution summary and stats.
    """
    root = project_root or Path.cwd()
    resolved_pdf = pdf_path or (
        DEFAULT_PDF_PATH if DEFAULT_PDF_PATH.exists() else (root / FALLBACK_PDF_PATH)
    )

    if not resolved_pdf.exists():
        raise FileNotFoundError(f"Source PDF does not exist: {resolved_pdf}")

    prompts_dir = root / "data" / "direct_translation" / "prompts"
    chunks_dir = root / "data" / "direct_translation" / "input_chunks"
    translations_dir = root / "data" / "direct_translation" / "translations"
    book_file = translations_dir / "sri_ramcharitmanas_russian_edition.md"

    master_prompt = prompts_dir / "master_system_prompt.txt"
    working_prompt = prompts_dir / "working_fragment_prompt.txt"

    # Step 1: Split chunk PDF
    logger.info(f"Splitting PDF chunk: pages {start_page}..{start_page + num_pages - 1}")
    chunk_path, actual_start, actual_end = split_pdf_chunk(
        source_pdf_path=resolved_pdf,
        start_page=start_page,
        num_pages=num_pages,
        output_dir=chunks_dir,
    )

    # Step 2: Translate via multimodal Gemini
    logger.info(f"Translating chunk with model {model_name}...")
    result = translate_pdf_chunk(
        chunk_pdf_path=chunk_path,
        master_prompt_path=master_prompt,
        working_prompt_path=working_prompt,
        output_dir=translations_dir,
        model_name=model_name,
    )

    # Step 3: Append to continuous edition
    chars_appended = append_chunk_to_edition(
        chunk_markdown_path=result.output_markdown_path,
        book_markdown_path=book_file,
    )

    # Step 4: Sync docs/ for web reader
    stats = sync_web_reader(project_root=root)

    # Step 5: Optional publish to GitHub
    publish_status = False
    if auto_publish:
        commit_msg = (
            f"feat(translation): add pages {actual_start}-{actual_end} to Russian edition "
            f"({stats['percentage']}% completed)"
        )
        publish_status = publish_to_github(commit_msg, project_root=root, push=True)

    return {
        "start_page": actual_start,
        "end_page": actual_end,
        "output_path": str(result.output_markdown_path),
        "chars_appended": chars_appended,
        "last_completed_page": stats["last_completed_page"],
        "percentage": stats["percentage"],
        "duration_seconds": result.duration_seconds,
        "published_to_github": publish_status,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for translation orchestrator."""
    parser = argparse.ArgumentParser(
        description="Automated orchestrator for direct translation, book compilation, and publishing."
    )
    parser.add_argument(
        "--start-page",
        type=int,
        required=True,
        help="1-based starting page number.",
    )
    parser.add_argument(
        "--num-pages",
        type=int,
        default=15,
        help="Number of pages in the chunk (default: 15).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.5-flash-lite",
        help="Gemini model name (default: gemini-3.5-flash-lite).",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Skip automatic git commit and push.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for orchestrator."""
    args = parse_args(argv)
    try:
        summary = run_pipeline_chunk(
            start_page=args.start_page,
            num_pages=args.num_pages,
            model_name=args.model,
            auto_publish=not args.no_publish,
        )
        print("\n" + "=" * 70)
        print("ORCHESTRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"Pages:               {summary['start_page']}–{summary['end_page']}")
        print(f"Appended Characters: {summary['chars_appended']}")
        print(f"Total Completed:     {summary['last_completed_page']}/1200 ({summary['percentage']}%)")
        print(f"Duration:            {summary['duration_seconds']:.2f}s")
        print(f"Published to GitHub: {summary['published_to_github']}")
        print("=" * 70 + "\n")
        return 0
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
