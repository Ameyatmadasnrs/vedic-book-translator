"""Direct PDF translation engine sending PDF chunks directly to Gemini multimodal API."""

import os
import time
from dataclasses import dataclass
from pathlib import Path

import dotenv
import pymupdf
from loguru import logger


@dataclass
class DirectTranslationResult:
    """Result of a direct PDF translation run."""

    start_page: int
    end_page: int
    num_pages: int
    chunk_pdf_path: Path
    output_markdown_path: Path
    model_name: str
    translation_text: str
    duration_seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None


def resolve_api_key(project_root: Path | None = None) -> str:
    """Resolve Gemini API key from .env without exposing or logging it."""
    root = project_root or Path.cwd()
    env_file = root / ".env"
    if env_file.exists():
        dotenv.load_dotenv(env_file)

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "GEMINI_API_KEY is not configured. Please ensure it is present in .env."
        )
    return key


def split_pdf_chunk(
    source_pdf_path: Path,
    start_page: int,
    num_pages: int,
    output_dir: Path,
) -> tuple[Path, int, int]:
    """Extract a range of pages from source PDF into a self-contained sub-PDF.

    Args:
        source_pdf_path: Path to the complete source PDF.
        start_page: 1-based starting page number.
        num_pages: Number of pages to extract.
        output_dir: Directory where chunk PDF should be written.

    Returns:
        Tuple of (chunk_pdf_path, actual_start_page, actual_end_page).
    """
    if not source_pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf_path}")
    if start_page < 1:
        raise ValueError(f"start_page must be >= 1, got {start_page}")
    if num_pages < 1:
        raise ValueError(f"num_pages must be >= 1, got {num_pages}")

    output_dir.mkdir(parents=True, exist_ok=True)

    src_doc = pymupdf.open(source_pdf_path)
    total_pages = src_doc.page_count

    from_idx = start_page - 1
    if from_idx >= total_pages:
        src_doc.close()
        raise ValueError(
            f"start_page {start_page} exceeds total pages ({total_pages}) in {source_pdf_path.name}"
        )

    to_idx = min(total_pages - 1, from_idx + num_pages - 1)
    end_page = to_idx + 1

    chunk_pdf_path = output_dir / f"chunk_pages_{start_page}_{end_page}.pdf"

    chunk_doc = pymupdf.open()
    chunk_doc.insert_pdf(src_doc, from_page=from_idx, to_page=to_idx)
    chunk_doc.save(chunk_pdf_path)
    chunk_doc.close()
    src_doc.close()

    logger.info(
        f"Created PDF chunk: {chunk_pdf_path.name} (pages {start_page}–{end_page}, "
        f"{chunk_pdf_path.stat().st_size} bytes)"
    )
    return chunk_pdf_path, start_page, end_page


def translate_pdf_chunk(
    chunk_pdf_path: Path,
    master_prompt_path: Path,
    working_prompt_path: Path,
    output_dir: Path,
    model_name: str = "gemini-3.5-flash-lite",
    project_root: Path | None = None,
    temperature: float = 0.2,
) -> DirectTranslationResult:
    """Send a PDF chunk directly to Gemini API and save the complete Russian translation.

    Args:
        chunk_pdf_path: Path to the extracted sub-PDF chunk.
        master_prompt_path: Path to the master system instruction file.
        working_prompt_path: Path to the per-fragment instruction file.
        output_dir: Directory where the Russian translation markdown should be saved.
        model_name: Gemini model identifier.
        project_root: Repository root path.
        temperature: Model temperature.

    Returns:
        DirectTranslationResult containing file paths, translation text, and metrics.
    """
    if not chunk_pdf_path.exists():
        raise FileNotFoundError(f"Chunk PDF not found: {chunk_pdf_path}")
    if not master_prompt_path.exists():
        raise FileNotFoundError(f"Master prompt not found: {master_prompt_path}")
    if not working_prompt_path.exists():
        raise FileNotFoundError(f"Working prompt not found: {working_prompt_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load prompts
    master_prompt = master_prompt_path.read_text(encoding="utf-8").strip()
    working_prompt = working_prompt_path.read_text(encoding="utf-8").strip()

    # 2. Extract page range numbers from filename (chunk_pages_{start}_{end}.pdf)
    stem_parts = chunk_pdf_path.stem.split("_")
    start_page = int(stem_parts[2]) if len(stem_parts) >= 4 and stem_parts[2].isdigit() else 1
    end_page = int(stem_parts[3]) if len(stem_parts) >= 4 and stem_parts[3].isdigit() else start_page
    num_pages = end_page - start_page + 1

    # 3. Initialize Gemini client
    api_key = resolve_api_key(project_root)
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # 4. Upload PDF chunk to Gemini Files API
    logger.info(f"Uploading {chunk_pdf_path.name} to Gemini Files API...")
    uploaded_file = client.files.upload(file=str(chunk_pdf_path))
    logger.info(f"PDF uploaded successfully: {uploaded_file.name}")

    start_time = time.perf_counter()
    translation_text = ""
    input_tokens = None
    output_tokens = None

    try:
        logger.info(
            f"Requesting direct translation from model {model_name} for pages {start_page}–{end_page}..."
        )
        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_file, working_prompt],
            config=types.GenerateContentConfig(
                system_instruction=master_prompt,
                temperature=temperature,
            ),
        )
        translation_text = response.text or ""
        duration = time.perf_counter() - start_time

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)

        logger.info(
            f"Translation received in {duration:.1f}s ({len(translation_text)} chars, "
            f"tokens: in={input_tokens}, out={output_tokens})"
        )
    finally:
        # Clean up remote file on Gemini storage
        try:
            if uploaded_file.name:
                client.files.delete(name=uploaded_file.name)
                logger.debug(f"Deleted remote file {uploaded_file.name} from Gemini storage")
        except Exception as e:
            logger.warning(f"Could not delete remote file {uploaded_file.name}: {e}")

    # 5. Format and save translation output
    output_path = output_dir / f"translation_pages_{start_page}_{end_page}.md"

    header_block = (
        f"# Перевод «Шри Рамачаритаманаса» (Gita Press)\n"
        f"**Фрагмент:** Страницы {start_page}–{end_page} (всего {num_pages} стр.)  \n"
        f"**Модель ИИ:** `{model_name}`  \n"
        f"**Метод перевода:** Direct Multimodal PDF Translation  \n"
        f"**Дата создания:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n\n"
        f"---\n\n"
    )

    full_output = header_block + translation_text.strip() + "\n"
    output_path.write_text(full_output, encoding="utf-8")
    logger.info(f"Saved Russian translation to: {output_path}")

    return DirectTranslationResult(
        start_page=start_page,
        end_page=end_page,
        num_pages=num_pages,
        chunk_pdf_path=chunk_pdf_path,
        output_markdown_path=output_path,
        model_name=model_name,
        translation_text=translation_text,
        duration_seconds=duration,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
