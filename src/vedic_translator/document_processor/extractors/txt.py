"""Plain text and Markdown document extractor."""

from pathlib import Path
import re
from typing import List, Set

from loguru import logger

from vedic_translator.core.exceptions import CorruptedDocumentError, UnsupportedFormatError
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


class TXTExtractor(BaseExtractor):
    """Extractor for plain text (.txt, .text) and Markdown (.md) documents."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".txt", ".text", ".md"}

    def _read_content_with_encodings(self, file_path: Path) -> str:
        """Attempt to read file with safe fallback encodings without modifying file."""
        encodings = ["utf-8", "utf-8-sig", "utf-16", "cp1251", "latin-1"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        raise CorruptedDocumentError(
            f"Unable to decode text document with any supported encoding: {file_path}"
        )

    def extract(self, file_path: Path) -> Document:
        """Extract plain text or markdown document into canonical Document AST."""
        if not self.supports(file_path):
            raise UnsupportedFormatError(f"TXTExtractor does not support {file_path.suffix}")

        validate_source_file(file_path)
        raw_text = self._read_content_with_encodings(file_path)

        if not raw_text.strip():
            raise CorruptedDocumentError(f"Document contains only whitespace: {file_path}")

        logger.info(f"Extracting text document: {file_path.name} ({len(raw_text)} chars)")
        metadata = self._build_initial_metadata(file_path)

        # Split into raw paragraphs (delimited by two or more newlines)
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_text) if p.strip()]

        chapters: List[Chapter] = []
        current_chapter: Chapter | None = None
        current_section: Section | None = None
        chapter_idx = 1
        section_idx = 1
        seq_idx = 0

        # Patterns for chapter / section detection
        md_h1_pattern = re.compile(r"^#\s+(.+)$")
        md_h2_pattern = re.compile(r"^##\s+(.+)$")
        chapter_pattern = re.compile(
            r"^(?:Chapter|Глава|Canto|Песнь)\s+([IVXLCDM\d]+[:.\s\-–—]?[^\n]*)",
            re.IGNORECASE,
        )
        section_pattern = re.compile(
            r"^(?:Text|Текст|Verse|Стих|Section)\s+([IVXLCDM\d]+[:.\s\-–—]?[^\n]*)",
            re.IGNORECASE,
        )

        for para in raw_paragraphs:
            # Check for Chapter Heading (e.g. # Chapter, or "Chapter 1: ...")
            h1_match = md_h1_pattern.match(para)
            ch_match = chapter_pattern.match(para)

            if h1_match or ch_match:
                title = h1_match.group(1).strip() if h1_match else para.strip()
                current_chapter = Chapter(chapter_index=chapter_idx, title=title)
                chapters.append(current_chapter)
                chapter_idx += 1
                section_idx = 1

                # Add heading block
                heading_block = Block(
                    type=BlockType.HEADING,
                    source_text=title,
                    state=BlockState.INGESTED,
                    sequence_index=seq_idx,
                )
                seq_idx += 1
                current_section = Section(section_index=section_idx, heading=title, blocks=[heading_block])
                current_chapter.sections.append(current_section)
                section_idx += 1
                continue

            # Check for Section / Verse Heading (e.g. ## Section or "Text 1")
            h2_match = md_h2_pattern.match(para)
            sec_match = section_pattern.match(para)

            if h2_match or sec_match:
                sec_title = h2_match.group(1).strip() if h2_match else para.strip()
                if current_chapter is None:
                    current_chapter = Chapter(chapter_index=chapter_idx, title="Introduction")
                    chapters.append(current_chapter)
                    chapter_idx += 1

                heading_block = Block(
                    type=BlockType.SUBHEADING,
                    source_text=sec_title,
                    state=BlockState.INGESTED,
                    sequence_index=seq_idx,
                )
                seq_idx += 1
                current_section = Section(section_index=section_idx, heading=sec_title, blocks=[heading_block])
                current_chapter.sections.append(current_section)
                section_idx += 1
                continue

            # Regular narrative paragraph
            if current_chapter is None:
                current_chapter = Chapter(chapter_index=chapter_idx, title=file_path.stem)
                chapters.append(current_chapter)
                chapter_idx += 1

            if current_section is None:
                current_section = Section(section_index=section_idx, heading=None)
                current_chapter.sections.append(current_section)
                section_idx += 1

            block = Block(
                type=BlockType.PARAGRAPH,
                source_text=para,
                state=BlockState.INGESTED,
                sequence_index=seq_idx,
            )
            seq_idx += 1
            current_section.blocks.append(block)

        # Set title if first chapter has a heading title
        if chapters and chapters[0].title:
            metadata.title = chapters[0].title

        doc = Document(metadata=metadata, chapters=chapters)
        logger.info(
            f"Extracted {doc.total_blocks()} blocks across {len(chapters)} chapters from {file_path.name}"
        )
        return doc
