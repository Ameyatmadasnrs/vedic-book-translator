"""Command-line interface for Direct PDF Translation MVP."""

import argparse
import sys
from pathlib import Path

from loguru import logger

from vedic_translator.direct_translation.translator import (
    split_pdf_chunk,
    translate_pdf_chunk,
)

DEFAULT_PDF_PATH = Path(
    r"C:\Users\Ameya\Desktop\Amar\Рамаяна\Ramcharita Manas (Hindi & English Translation) Gita Press.pdf"
)
FALLBACK_PDF_PATH = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for direct PDF translation."""
    parser = argparse.ArgumentParser(
        description="Direct PDF Translation MVP: Multimodal PDF translation into literary Russian via Gemini."
    )
    parser.add_argument(
        "--pdf-path",
        type=str,
        default=str(DEFAULT_PDF_PATH if DEFAULT_PDF_PATH.exists() else FALLBACK_PDF_PATH),
        help="Path to source PDF file.",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=215,
        help="1-based starting page number (default: 215).",
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
        help="Gemini model ID (default: gemini-3.5-flash-lite).",
    )
    parser.add_argument(
        "--prompts-dir",
        type=str,
        default="data/direct_translation/prompts",
        help="Directory containing prompt files.",
    )
    parser.add_argument(
        "--chunks-dir",
        type=str,
        default="data/direct_translation/input_chunks",
        help="Directory to save extracted PDF chunks.",
    )
    parser.add_argument(
        "--translations-dir",
        type=str,
        default="data/direct_translation/translations",
        help="Directory to save generated translations.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Model sampling temperature (default: 0.2).",
    )
    return parser.parse_args(args)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for direct PDF translation."""
    args = parse_args(argv)

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"Source PDF does not exist: {pdf_path}")
        return 1

    prompts_dir = Path(args.prompts_dir)
    master_prompt_path = prompts_dir / "master_system_prompt.txt"
    working_prompt_path = prompts_dir / "working_fragment_prompt.txt"

    if not master_prompt_path.exists() or not working_prompt_path.exists():
        logger.error(
            f"Prompt files missing in {prompts_dir}. Ensure master_system_prompt.txt "
            f"and working_fragment_prompt.txt exist."
        )
        return 1

    chunks_dir = Path(args.chunks_dir)
    translations_dir = Path(args.translations_dir)

    logger.info("=== DIRECT PDF TRANSLATION MVP ===")
    logger.info(f"Source PDF:   {pdf_path}")
    logger.info(f"Start Page:   {args.start_page}")
    logger.info(f"Num Pages:    {args.num_pages}")
    logger.info(f"Target Model: {args.model}")

    # Step 1: Split chunk from source PDF
    chunk_path, start_page, end_page = split_pdf_chunk(
        source_pdf_path=pdf_path,
        start_page=args.start_page,
        num_pages=args.num_pages,
        output_dir=chunks_dir,
    )

    # Step 2: Send PDF chunk directly to Gemini
    result = translate_pdf_chunk(
        chunk_pdf_path=chunk_path,
        master_prompt_path=master_prompt_path,
        working_prompt_path=working_prompt_path,
        output_dir=translations_dir,
        model_name=args.model,
        temperature=args.temperature,
    )

    print("\n" + "=" * 70)
    print("DIRECT TRANSLATION COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Pages Translated: {result.start_page}–{result.end_page} ({result.num_pages} pages)")
    print(f"Model Used:       {result.model_name}")
    print(f"PDF Chunk Path:   {result.chunk_pdf_path}")
    print(f"Output Saved To:  {result.output_markdown_path}")
    print(f"Output Length:    {len(result.translation_text)} characters")
    print(f"Duration:         {result.duration_seconds:.2f} seconds")
    if result.input_tokens and result.output_tokens:
        print(f"Tokens:           Input: {result.input_tokens}, Output: {result.output_tokens}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
