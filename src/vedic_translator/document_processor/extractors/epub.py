"""EPUB digital book extractor."""

from pathlib import Path
from typing import List, Set
import zipfile

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
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


class EPUBExtractor(BaseExtractor):
    """Extractor for EPUB 2 and EPUB 3 digital books."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".epub"}

    def extract(self, file_path: Path) -> Document:
        """Extract EPUB document into canonical Document AST preserving reading order."""
        if not self.supports(file_path):
            raise UnsupportedFormatError(f"EPUBExtractor does not support {file_path.suffix}")

        validate_source_file(file_path)

        try:
            # Read EPUB in read-only mode
            book = epub.read_epub(str(file_path))
        except (zipfile.BadZipFile, Exception) as exc:
            raise CorruptedDocumentError(
                f"Failed to read EPUB file. File is corrupt or invalid: {file_path}",
                details={"error": str(exc)},
            ) from exc

        metadata = self._build_initial_metadata(file_path)

        # Extract Dublin Core metadata
        try:
            titles = book.get_metadata("DC", "title")
            if titles and titles[0][0]:
                metadata.title = str(titles[0][0])
            creators = book.get_metadata("DC", "creator")
            if creators and creators[0][0]:
                metadata.author = str(creators[0][0])
            langs = book.get_metadata("DC", "language")
            if langs and langs[0][0]:
                metadata.source_language = str(langs[0][0])
            publishers = book.get_metadata("DC", "publisher")
            if publishers and publishers[0][0]:
                metadata.publisher = str(publishers[0][0])
        except Exception as e:
            logger.warning(f"Could not read EPUB Dublin Core metadata from {file_path.name}: {e}")

        logger.info(f"Extracting EPUB document: {file_path.name} (Title: '{metadata.title}')")

        chapters: List[Chapter] = []
        current_chapter: Chapter | None = None
        current_section: Section | None = None
        chapter_idx = 1
        section_idx = 1
        seq_idx = 0
        total_chars = 0

        # Traverse spine to preserve canonical reading order
        spine_items = [entry[0] for entry in book.spine if isinstance(entry, (tuple, list))]

        for item_id in spine_items:
            # Skip navigation items (TOC, NCX, NAV)
            if item_id.lower() in ["nav", "toc", "ncx"]:
                continue

            item = book.get_item_with_id(item_id)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            if "nav" in item.get_name().lower() or "toc" in item.get_name().lower():
                continue

            soup = BeautifulSoup(item.get_content(), "html.parser")
            body = soup.find("body") or soup

            # Process block elements in body preserving flow
            for elem in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "li"]):
                text = elem.get_text().strip()
                if not text:
                    continue

                total_chars += len(text)
                tag_name = elem.name.lower()

                # Chapter Heading: <h1>
                if tag_name == "h1":
                    # If an empty placeholder chapter was created, update its title
                    has_content = (
                        current_chapter is not None
                        and any(b.type != BlockType.HEADING for s in current_chapter.sections for b in s.blocks)
                    )
                    if current_chapter is not None and not has_content:
                        current_chapter.title = text
                    else:
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

                # Section Heading: <h2> or <h3>
                if tag_name in ["h2", "h3"]:
                    if current_chapter is None:
                        current_chapter = Chapter(chapter_index=chapter_idx, title=metadata.title)
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

                # Regular paragraph / blockquote / list item
                if current_chapter is None:
                    current_chapter = Chapter(chapter_index=chapter_idx, title=metadata.title)
                    chapters.append(current_chapter)
                    chapter_idx += 1

                if current_section is None:
                    current_section = Section(section_index=section_idx, heading=None)
                    current_chapter.sections.append(current_section)
                    section_idx += 1

                b_type = BlockType.QUOTE if tag_name == "blockquote" else BlockType.PARAGRAPH
                current_section.blocks.append(
                    Block(
                        type=b_type,
                        source_text=text,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                    )
                )
                seq_idx += 1

        if total_chars == 0:
            raise CorruptedDocumentError(f"EPUB document contains no readable text: {file_path}")

        doc = Document(metadata=metadata, chapters=chapters)
        logger.info(
            f"Extracted {doc.total_blocks()} blocks across {len(chapters)} chapters from {file_path.name}"
        )
        return doc
