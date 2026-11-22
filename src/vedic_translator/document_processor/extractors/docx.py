"""Microsoft Word (.docx) document extractor."""

from pathlib import Path
import re
from typing import List, Set
import zipfile

import docx
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
    def supported_extensions(self) -> Set[str]:
        return {".docx"}

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

        chapters: List[Chapter] = []
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

        for p in doc_obj.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            total_chars += len(text)
            style_name = p.style.name.lower() if p.style else ""

            # Check if this paragraph is a Chapter Heading
            is_h1 = any(
                h in style_name
                for h in ["heading 1", "заголовок 1", "title", "титул"]
            )
            is_ch_text = bool(chapter_regex.match(text))

            if is_h1 or is_ch_text:
                current_chapter = Chapter(chapter_index=chapter_idx, title=text)
                chapters.append(current_chapter)
                chapter_idx += 1
                section_idx = 1

                heading_block = Block(
                    type=BlockType.HEADING,
                    source_text=text,
                    state=BlockState.INGESTED,
                    sequence_index=seq_idx,
                )
                seq_idx += 1
                current_section = Section(section_index=section_idx, heading=text, blocks=[heading_block])
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

                subheading_block = Block(
                    type=BlockType.SUBHEADING,
                    source_text=text,
                    state=BlockState.INGESTED,
                    sequence_index=seq_idx,
                )
                seq_idx += 1
                current_section = Section(section_index=section_idx, heading=text, blocks=[subheading_block])
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
            )
            seq_idx += 1
            current_section.blocks.append(block)

        # Handle tables if present
        for table in doc_obj.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if not row_texts:
                    continue
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

                current_section.blocks.append(
                    Block(
                        type=BlockType.PARAGRAPH,
                        source_text=row_str,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata={"is_table_row": True},
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
