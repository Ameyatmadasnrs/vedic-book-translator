"""Digital PDF document extractor using PyMuPDF (fitz)."""

import re
from pathlib import Path
from typing import Any

import pymupdf as fitz
from loguru import logger

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    UnsupportedFormatError,
)
from vedic_translator.core.models import (
    Block,
    BlockState,
    BlockType,
    Chapter,
    Document,
    Section,
)
from vedic_translator.document_processor.extractors.base import (
    BaseExtractor,
    validate_source_file,
)


class PDFExtractor(BaseExtractor):
    """Extractor for text-based (digital) PDF documents."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    def extract(self, file_path: Path) -> Document:
        """Extract text-based PDF document into canonical Document AST preserving reading order."""
        if not self.supports(file_path):
            raise UnsupportedFormatError(f"PDFExtractor does not support {file_path.suffix}")

        validate_source_file(file_path)

        try:
            # Open PDF in read-only mode using PyMuPDF
            doc_obj = fitz.open(str(file_path))
        except Exception as exc:
            raise CorruptedDocumentError(
                f"Failed to open PDF document. File is corrupt or invalid: {file_path}",
                details={"error": str(exc)},
            ) from exc

        if doc_obj.is_encrypted:
            doc_obj.close()
            raise CorruptedDocumentError(f"PDF is encrypted/password-protected: {file_path}")

        metadata = self._build_initial_metadata(file_path)

        # Extract PDF metadata
        try:
            pdf_meta = doc_obj.metadata or {}
            if pdf_meta.get("title") and pdf_meta["title"].strip():
                metadata.title = pdf_meta["title"].strip()
            if pdf_meta.get("author") and pdf_meta["author"].strip():
                metadata.author = pdf_meta["author"].strip()
            if pdf_meta.get("subject") and pdf_meta["subject"].strip():
                metadata.custom_fields["subject"] = pdf_meta["subject"].strip()
        except Exception as e:
            logger.warning(f"Could not read PDF metadata from {file_path.name}: {e}")

        logger.info(f"Extracting digital PDF: {file_path.name} ({len(doc_obj)} pages)")

        # Build page-to-chapter mapping from Table of Contents (bookmarks) if present
        toc_page_map: dict[int, str] = {}
        try:
            toc = doc_obj.get_toc()
            for item in toc:
                # toc item format: [level, title, page_number]
                if len(item) >= 3 and item[0] in [1, 2]:
                    _lvl, title, pno = item[0], str(item[1]).strip(), int(item[2])
                    if pno > 0 and pno not in toc_page_map:
                        toc_page_map[pno] = title
        except Exception as e:
            logger.debug(f"No Table of Contents extracted from {file_path.name}: {e}")

        chapters: list[Chapter] = []
        current_chapter: Chapter | None = None
        current_section: Section | None = None
        chapter_idx = 1
        section_idx = 1
        seq_idx = 0
        total_chars = 0

        chapter_regex = re.compile(
            r"^(?:Chapter|Глава|Canto|Песнь)\s+([IVXLCDM\d]+[:.\s\-–—]?[^\n]*)",
            re.IGNORECASE,
        )

        try:
            for page_index in range(len(doc_obj)):
                page = doc_obj[page_index]
                page_num = page_index + 1

                # Check if this page marks the start of a TOC chapter
                if page_num in toc_page_map:
                    ch_title = toc_page_map[page_num]
                    current_chapter = Chapter(chapter_index=chapter_idx, title=ch_title)
                    chapters.append(current_chapter)
                    chapter_idx += 1
                    section_idx = 1

                    heading_block = Block(
                        type=BlockType.HEADING,
                        source_text=ch_title,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata={"page": page_num, "from_toc": True},
                    )
                    seq_idx += 1
                    current_section = Section(
                        section_index=section_idx, heading=ch_title, blocks=[heading_block]
                    )
                    current_chapter.sections.append(current_section)
                    section_idx += 1

                # Extract text blocks in reading order
                # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
                # block_type == 0 indicates text
                blocks = page.get_text("blocks")
                p_dict = page.get_text("dict") or {}
                dict_blocks = [
                    db
                    for db in p_dict.get("blocks", [])
                    if isinstance(db, dict) and db.get("type", 0) == 0
                ]

                for b in blocks:
                    if b[6] != 0:  # Skip image blocks
                        continue

                    # Preserve exact source text including any non-breaking spaces (\xa0)
                    block_text = b[4].strip()
                    if not block_text:
                        continue

                    total_chars += len(block_text)
                    bbox_coords = [round(coord, 2) for coord in b[:4]]

                    # Extract font properties by matching with dict spans
                    font_info: dict[str, Any] = {}
                    if dict_blocks:
                        best_db = min(
                            dict_blocks,
                            key=lambda db: (
                                abs(db.get("bbox", (0, 0, 0, 0))[0] - b[0])
                                + abs(db.get("bbox", (0, 0, 0, 0))[1] - b[1])
                            ),
                        )
                        spans = [
                            s
                            for line in best_db.get("lines", [])
                            for s in line.get("spans", [])
                            if s.get("text", "").strip()
                        ]
                        if spans:
                            sizes = [s["size"] for s in spans if "size" in s]
                            fonts = list({s["font"] for s in spans if "font" in s})
                            is_bold = any(
                                bool(s.get("flags", 0) & 2) or "bold" in s.get("font", "").lower()
                                for s in spans
                            )
                            is_italic = any(
                                bool(s.get("flags", 0) & 1)
                                or "italic" in s.get("font", "").lower()
                                or "oblique" in s.get("font", "").lower()
                                for s in spans
                            )
                            if sizes:
                                font_info["font_size"] = round(max(sizes), 2)
                            if fonts:
                                font_info["fonts"] = fonts
                            if is_bold:
                                font_info["is_bold"] = True
                            if is_italic:
                                font_info["is_italic"] = True

                    block_meta: dict[str, Any] = {
                        "page": page_num,
                        "bbox": bbox_coords,
                        **font_info,
                    }

                    # For chapter title comparisons and matching, compare normalized whitespace
                    # so that variations in space characters (e.g., U+00A0 vs U+0020) do not prevent matching
                    norm_text = block_text.replace("\xa0", " ")
                    norm_title = (
                        current_chapter.title.replace("\xa0", " ") if current_chapter else ""
                    )

                    # If block text matches current chapter title, avoid creating duplicate chapter
                    if current_chapter and (
                        norm_text == norm_title
                        or norm_text in norm_title
                        or norm_title in norm_text
                    ):
                        # Ensure the heading block has bbox and font metadata
                        if current_section and current_section.blocks:
                            first_b = current_section.blocks[0]
                            if first_b.type == BlockType.HEADING:
                                first_b.metadata["bbox"] = bbox_coords
                                for k, v in font_info.items():
                                    first_b.metadata[k] = v
                        continue

                    # Fallback chapter detection: only when document has no TOC bookmarks
                    ch_match = chapter_regex.match(norm_text) if not toc_page_map else None
                    if ch_match and len(block_text.splitlines()) <= 2:
                        current_chapter = Chapter(chapter_index=chapter_idx, title=block_text)
                        chapters.append(current_chapter)
                        chapter_idx += 1
                        section_idx = 1

                        heading_block = Block(
                            type=BlockType.HEADING,
                            source_text=block_text,
                            state=BlockState.INGESTED,
                            sequence_index=seq_idx,
                            metadata=dict(block_meta),
                        )
                        seq_idx += 1
                        current_section = Section(
                            section_index=section_idx, heading=block_text, blocks=[heading_block]
                        )
                        current_chapter.sections.append(current_section)
                        section_idx += 1
                        continue

                    # Standard text paragraph
                    if current_chapter is None:
                        current_chapter = Chapter(chapter_index=chapter_idx, title=metadata.title)
                        chapters.append(current_chapter)
                        chapter_idx += 1

                    if current_section is None:
                        current_section = Section(section_index=section_idx, heading=None)
                        current_chapter.sections.append(current_section)
                        section_idx += 1

                    block = Block(
                        type=BlockType.PARAGRAPH,
                        source_text=block_text,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata=dict(block_meta),
                    )
                    seq_idx += 1
                    current_section.blocks.append(block)

        finally:
            doc_obj.close()

        if total_chars == 0:
            raise CorruptedDocumentError(
                f"PDF document contains no digital text layer: {file_path}. "
                "Scanned documents require the OCR subsystem."
            )

        doc = Document(metadata=metadata, chapters=chapters)
        logger.info(
            f"Extracted {doc.total_blocks()} blocks across {len(chapters)} chapters from {file_path.name}"
        )
        return doc
