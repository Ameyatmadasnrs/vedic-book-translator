"""Microsoft Word (.docx) document extractor."""

import re
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
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


class DOCXExtractor(BaseExtractor):
    """Extractor for Microsoft Word (.docx) documents."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".docx"}

    def _is_docx_header_row(self, row: Any) -> bool:
        """Check if a python-docx row has the w:tblHeader property set."""
        tr_pr = getattr(row._tr, "trPr", None)
        if tr_pr is None:
            return False
        for child in tr_pr:
            if child.tag.endswith("}tblHeader"):
                val = child.get(qn("w:val"))
                if val in ("0", "false", "off"):
                    return False
                return True
        return False

    def extract(self, file_path: Path) -> Document:
        """Extract DOCX document into canonical Document AST."""
        if not self.supports(file_path):
            raise UnsupportedFormatError(f"DOCXExtractor does not support {file_path.suffix}")

        validate_source_file(file_path)

        try:
            # Open in read-only mode using python-docx
            doc_obj = docx.Document(str(file_path))
        except (zipfile.BadZipFile, Exception) as exc:
            raise CorruptedDocumentError(
                f"Failed to read DOCX file. File is corrupt or invalid: {file_path}",
                details={"error": str(exc)},
            ) from exc

        # Extract document properties
        metadata = self._build_initial_metadata(file_path)
        try:
            core_props = doc_obj.core_properties
            if core_props.title and core_props.title.strip():
                metadata.title = core_props.title.strip()
            if core_props.author and core_props.author.strip():
                metadata.author = core_props.author.strip()
            if core_props.language:
                metadata.source_language = core_props.language.strip()
        except Exception as e:
            logger.warning(f"Could not read DOCX core properties from {file_path.name}: {e}")

        logger.info(f"Extracting DOCX document: {file_path.name}")

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

        for child in doc_obj.element.body:
            if child.tag.endswith("}p"):
                p = Paragraph(child, doc_obj)
                text = p.text.strip()
                if not text:
                    continue

                total_chars += len(text)
                orig_style_name = p.style.name if p.style else ""
                style_name = orig_style_name.lower()

                para_meta: dict[str, Any] = {}
                if orig_style_name:
                    para_meta["style_name"] = orig_style_name

                # Check heading levels
                for lvl in range(1, 10):
                    if f"heading {lvl}" in style_name or f"заголовок {lvl}" in style_name:
                        para_meta["heading_level"] = lvl
                        break
                if "title" in style_name or "титул" in style_name:
                    para_meta["heading_level"] = 1
                elif "subtitle" in style_name:
                    para_meta["heading_level"] = 2

                # Check list items from style name
                if "list" in style_name or "bullet" in style_name:
                    para_meta["is_list"] = True

                # Check Word XML numbering properties (w:numPr) for direct list formatting
                num_pr = getattr(getattr(p._p, "pPr", None), "numPr", None)
                if num_pr is not None:
                    para_meta["is_list"] = True
                    para_meta["numPr"] = True
                    ilvl_elem = getattr(num_pr, "ilvl", None)
                    if ilvl_elem is not None and getattr(ilvl_elem, "val", None) is not None:
                        try:
                            ilvl_int = int(ilvl_elem.val)
                            para_meta["list_level"] = ilvl_int
                            para_meta["ilvl"] = ilvl_int
                        except (ValueError, TypeError):
                            pass
                    num_id_elem = getattr(num_pr, "numId", None)
                    if num_id_elem is not None and getattr(num_id_elem, "val", None) is not None:
                        try:
                            para_meta["num_id"] = int(num_id_elem.val)
                        except (ValueError, TypeError):
                            pass

                # Check if this paragraph is a Chapter Heading
                is_h1 = any(h in style_name for h in ["heading 1", "заголовок 1", "title", "титул"])
                is_ch_text = bool(chapter_regex.match(text))

                if is_h1 or is_ch_text:
                    current_chapter = Chapter(chapter_index=chapter_idx, title=text)
                    chapters.append(current_chapter)
                    chapter_idx += 1
                    section_idx = 1

                    heading_meta = dict(para_meta)
                    if "heading_level" not in heading_meta:
                        heading_meta["heading_level"] = 1

                    heading_block = Block(
                        type=BlockType.HEADING,
                        source_text=text,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata=heading_meta,
                    )
                    seq_idx += 1
                    current_section = Section(
                        section_index=section_idx, heading=text, blocks=[heading_block]
                    )
                    current_chapter.sections.append(current_section)
                    section_idx += 1
                    continue

                # Check if this paragraph is a Section Heading
                is_h2 = any(
                    h in style_name
                    for h in ["heading 2", "heading 3", "заголовок 2", "заголовок 3", "subtitle"]
                )
                if is_h2:
                    if current_chapter is None:
                        current_chapter = Chapter(chapter_index=chapter_idx, title="Introduction")
                        chapters.append(current_chapter)
                        chapter_idx += 1

                    subheading_meta = dict(para_meta)
                    if "heading_level" not in subheading_meta:
                        subheading_meta["heading_level"] = 2

                    subheading_block = Block(
                        type=BlockType.SUBHEADING,
                        source_text=text,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata=subheading_meta,
                    )
                    seq_idx += 1
                    current_section = Section(
                        section_index=section_idx, heading=text, blocks=[subheading_block]
                    )
                    current_chapter.sections.append(current_section)
                    section_idx += 1
                    continue

                # Standard paragraph
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
                    source_text=text,
                    state=BlockState.INGESTED,
                    sequence_index=seq_idx,
                    metadata=dict(para_meta),
                )
                seq_idx += 1
                current_section.blocks.append(block)

            elif child.tag.endswith("}tbl"):
                table = Table(child, doc_obj)
                table_id = str(uuid4())
                total_rows = len(table.rows)
                for r_idx, row in enumerate(table.rows):
                    # Preserve all cells in order, preserving empty cells as empty strings
                    row_texts = [cell.text.strip() for cell in row.cells]
                    row_str = " | ".join(row_texts)
                    total_chars += len(row_str)

                    if current_chapter is None:
                        current_chapter = Chapter(chapter_index=chapter_idx, title=metadata.title)
                        chapters.append(current_chapter)
                        chapter_idx += 1

                    if current_section is None:
                        current_section = Section(section_index=section_idx, heading=None)
                        current_chapter.sections.append(current_section)
                        section_idx += 1

                    is_header = self._is_docx_header_row(row)

                    current_section.blocks.append(
                        Block(
                            type=BlockType.PARAGRAPH,
                            source_text=row_str,
                            state=BlockState.INGESTED,
                            sequence_index=seq_idx,
                            metadata={
                                "tag": "table",
                                "style_name": "Table",
                                "is_table_row": True,
                                "table_id": table_id,
                                "row_index": r_idx,
                                "total_rows": total_rows,
                                "cells_count": len(row_texts),
                                "cells": row_texts,
                                "is_header_row": is_header,
                            },
                        )
                    )
                    seq_idx += 1

        if total_chars == 0:
            raise CorruptedDocumentError(f"DOCX document contains no readable text: {file_path}")

        doc = Document(metadata=metadata, chapters=chapters)
        logger.info(
            f"Extracted {doc.total_blocks()} blocks across {len(chapters)} chapters from {file_path.name}"
        )
        return doc
