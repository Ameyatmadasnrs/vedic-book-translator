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
from vedic_translator.document_processor.extractors.font_normalizer import (
    LegacyFontNormalizer,
)

DEV_METRICAL_PREFIXES = (
    "दो0ó",
    "चौ0ó",
    "सो0ó",
    "छं0ó",
    "श्लोक",
    "सोरठा",
    "छन्द",
    "दोहा",
    "चौपाई",
)
IAST_METRICAL_PREFIXES = ("Do.:", "Cau.:", "So.:", "Chh.:", "Sloka:", "Chaṁ.:")
IAST_DIACRITICS = set("āīūṛṝḷḹṅñṭḍṇśṣḥṁĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤṀ")


class PDFExtractor(BaseExtractor):
    """Extractor for text-based (digital) PDF documents with span-level legacy font normalization."""

    def __init__(self, font_normalizer: LegacyFontNormalizer | None = None) -> None:
        self.font_normalizer = font_normalizer or LegacyFontNormalizer()

    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    def _classify_line_role(self, line_spans: list[dict[str, Any]], line_norm_text: str) -> str:
        """Deterministically determine the script/content role of an extracted line."""
        text = line_norm_text.strip()
        if not text:
            return "EMPTY"

        # 1. Check Devanagari metrical prefixes
        for m in DEV_METRICAL_PREFIXES:
            if text.startswith(m):
                return "DEVANAGARI"

        # 2. Check IAST metrical prefixes
        for m in IAST_METRICAL_PREFIXES:
            if text.startswith(m) or f" {m}" in text[:30]:
                return "TRANSLITERATION"

        # 3. Check font families and character composition
        dev_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
        alpha_count = sum(1 for ch in text if ch.isalpha())

        # Check Nalanda font distinctions (Nalandahel = Transliteration, Nalandatim = Prose)
        nalandahel_spans = [
            s
            for s in line_spans
            if "nalandahel" in s.get("font", "").lower() and s.get("raw_text", "").strip()
        ]
        nalandatim_spans = [
            s
            for s in line_spans
            if "nalandatim" in s.get("font", "").lower() and s.get("raw_text", "").strip()
        ]

        # If line contains English prose font (Nalandatim), it is PROSE unless it starts with a metrical marker
        if nalandatim_spans:
            return "PROSE"

        # Check if Chanakya font is used for meaningful text (not just borrowed nasal marks)
        chanakya_spans = [
            s
            for s in line_spans
            if "chanakya" in s.get("font", "").lower()
            and s.get("raw_text", "").strip() not in ("°", "Ú", " ", "")
        ]
        if chanakya_spans or (
            dev_count > 0 and alpha_count > 0 and (dev_count / alpha_count) >= 0.35
        ):
            return "DEVANAGARI"

        if nalandahel_spans and not nalandatim_spans:
            return "TRANSLITERATION"

        iast_char_count = sum(1 for ch in text if ch in IAST_DIACRITICS)
        if iast_char_count >= 2 and not nalandatim_spans and dev_count == 0:
            return "TRANSLITERATION"

        return "PROSE"

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

                # Extract text blocks in reading order from structured dictionary
                p_dict = page.get_text("dict") or {}
                dict_blocks = [
                    db
                    for db in p_dict.get("blocks", [])
                    if isinstance(db, dict) and db.get("type", 0) == 0
                ]

                for db in dict_blocks:
                    bbox_coords = [
                        round(coord, 2) for coord in db.get("bbox", (0.0, 0.0, 0.0, 0.0))
                    ]

                    processed_lines: list[dict[str, Any]] = []

                    for line in db.get("lines", []):
                        spans = line.get("spans", [])
                        line_has_nalanda = any(
                            self.font_normalizer.get_font_family(s.get("font", "")) == "nalanda"
                            for s in spans
                        )
                        span_norm_texts: list[str] = []
                        span_raw_texts: list[str] = []
                        line_pdf_spans: list[dict[str, Any]] = []
                        line_font_names: set[str] = set()
                        line_font_sizes: list[float] = []
                        line_has_bold = False
                        line_has_italic = False
                        line_has_legacy = False
                        prev_span_was_translit = False

                        for s in spans:
                            raw_text = s.get("text", "")
                            font_name = s.get("font", "")
                            size = round(s.get("size", 0.0), 2)
                            flags = s.get("flags", 0)
                            span_bbox = [round(c, 2) for c in s.get("bbox", (0.0, 0.0, 0.0, 0.0))]

                            # Normalize span using LegacyFontNormalizer
                            is_translit = line_has_nalanda or prev_span_was_translit
                            norm_text, was_converted, family = self.font_normalizer.normalize_span(
                                raw_text, font_name, is_transliteration=is_translit
                            )
                            if family == "nalanda" or "nalanda" in font_name.lower():
                                prev_span_was_translit = True
                            elif raw_text.strip():
                                prev_span_was_translit = False

                            if was_converted:
                                line_has_legacy = True

                            if raw_text.strip():
                                line_font_names.add(font_name)
                                line_font_sizes.append(size)
                                if bool(flags & 2) or "bold" in font_name.lower():
                                    line_has_bold = True
                                if (
                                    bool(flags & 1)
                                    or "italic" in font_name.lower()
                                    or "oblique" in font_name.lower()
                                ):
                                    line_has_italic = True

                            span_record: dict[str, Any] = {
                                "font": font_name,
                                "font_family": family,
                                "size": size,
                                "flags": flags,
                                "bbox": span_bbox,
                                "raw_text": raw_text,
                                "normalized_text": norm_text,
                                "converted": was_converted,
                            }
                            line_pdf_spans.append(span_record)
                            span_norm_texts.append(norm_text)
                            span_raw_texts.append(raw_text)

                        norm_line_str = "".join(span_norm_texts)
                        raw_line_str = "".join(span_raw_texts)
                        line_bbox = [round(c, 2) for c in line.get("bbox", (0.0, 0.0, 0.0, 0.0))]
                        role = self._classify_line_role(line_pdf_spans, norm_line_str)

                        processed_lines.append(
                            {
                                "role": role,
                                "norm_text": norm_line_str,
                                "raw_text": raw_line_str,
                                "bbox": line_bbox,
                                "pdf_spans": line_pdf_spans,
                                "font_names": line_font_names,
                                "font_sizes": line_font_sizes,
                                "has_bold": line_has_bold,
                                "has_italic": line_has_italic,
                                "has_legacy": line_has_legacy,
                            }
                        )

                    # Group contiguous lines by role into distinct sub-blocks
                    sub_blocks: list[dict[str, Any]] = []
                    cur_role: str | None = None
                    cur_lines: list[dict[str, Any]] = []

                    for pl in processed_lines:
                        r = pl["role"]
                        if r == "EMPTY":
                            if cur_lines:
                                cur_lines.append(pl)
                            continue
                        if r != cur_role and cur_lines:
                            sub_blocks.append({"role": cur_role, "lines": cur_lines})
                            cur_lines = []
                        cur_role = r
                        cur_lines.append(pl)

                    if cur_lines:
                        sub_blocks.append({"role": cur_role or "PROSE", "lines": cur_lines})

                    for sub in sub_blocks:
                        sub_lines = sub["lines"]
                        non_zero_bboxes = [
                            ln["bbox"] for ln in sub_lines if any(c != 0.0 for c in ln["bbox"])
                        ]
                        if non_zero_bboxes:
                            sub_bbox = [
                                round(min(b[0] for b in non_zero_bboxes), 2),
                                round(min(b[1] for b in non_zero_bboxes), 2),
                                round(max(b[2] for b in non_zero_bboxes), 2),
                                round(max(b[3] for b in non_zero_bboxes), 2),
                            ]
                        else:
                            sub_bbox = list(bbox_coords)

                        block_text = "\n".join(ln["norm_text"] for ln in sub_lines).strip()
                        # Canonicalize split matras across span boundaries
                        block_text = block_text.replace("\u093e\u0947", "\u094b").replace(
                            "\u093e\u0948", "\u094c"
                        )
                        raw_block_text = "\n".join(ln["raw_text"] for ln in sub_lines).strip()
                        if not block_text:
                            continue

                        total_chars += len(block_text)

                        sub_font_names = set().union(*(ln["font_names"] for ln in sub_lines))
                        sub_font_sizes = [sz for ln in sub_lines for sz in ln["font_sizes"]]
                        sub_has_bold = any(ln["has_bold"] for ln in sub_lines)
                        sub_has_italic = any(ln["has_italic"] for ln in sub_lines)
                        sub_has_legacy = any(ln["has_legacy"] for ln in sub_lines)
                        sub_pdf_spans = [sp for ln in sub_lines for sp in ln["pdf_spans"]]

                        font_info: dict[str, Any] = {}
                        if sub_font_sizes:
                            font_info["font_size"] = round(max(sub_font_sizes), 2)
                        if sub_font_names:
                            font_info["fonts"] = sorted(sub_font_names)
                        if sub_has_bold:
                            font_info["is_bold"] = True
                        if sub_has_italic:
                            font_info["is_italic"] = True

                        block_meta: dict[str, Any] = {
                            "page": page_num,
                            "bbox": sub_bbox,
                            "raw_source_text": raw_block_text,
                            "has_legacy_fonts": sub_has_legacy,
                            "pdf_spans": sub_pdf_spans,
                            "detected_script_role": sub["role"],
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
                            # Ensure the heading block has bbox, font and span metadata
                            if current_section and current_section.blocks:
                                first_b = current_section.blocks[0]
                                if first_b.type == BlockType.HEADING:
                                    first_b.metadata.update(block_meta)
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
                                section_index=section_idx,
                                heading=block_text,
                                blocks=[heading_block],
                            )
                            current_chapter.sections.append(current_section)
                            section_idx += 1
                            continue

                        # Standard text paragraph
                        if current_chapter is None:
                            current_chapter = Chapter(
                                chapter_index=chapter_idx, title=metadata.title
                            )
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
