"""EPUB digital book extractor."""

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import ebooklib
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
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
    def supported_extensions(self) -> set[str]:
        return {".epub"}

    def _populate_elem_meta(self, elem: Tag, target_meta: dict[str, Any], tag: str) -> None:
        """Populate base semantic attributes from an HTML element."""
        target_meta["tag"] = tag
        classes_val = elem.get("class")
        if isinstance(classes_val, str):
            classes_list = classes_val.split()
        elif isinstance(classes_val, list):
            classes_list = [str(c) for c in classes_val]
        else:
            classes_list = []
        if classes_list:
            target_meta["classes"] = classes_list
        elem_id = str(elem.get("id", "")).strip()
        if elem_id:
            target_meta["id"] = elem_id
        epub_type = str(elem.get("epub:type", "")).strip()
        if epub_type:
            target_meta["epub_type"] = epub_type

    def _extract_li(
        self, li: Tag, depth: int, list_type: str, context: dict[str, Any]
    ) -> Iterator[tuple[str, str, dict[str, Any]]]:
        """Extract a single list item and its nested lists in visual reading order."""
        direct_parts: list[str] = []
        nested: list[Tag] = []
        for c in li.children:
            if isinstance(c, Tag) and c.name.lower() in ["ul", "ol"]:
                nested.append(c)
            else:
                direct_parts.append(str(c) if isinstance(c, NavigableString) else c.get_text())
        text = "".join(direct_parts).strip()
        if text:
            meta = dict(context)
            li_classes_val = li.get("class")
            li_classes = (
                li_classes_val.split()
                if isinstance(li_classes_val, str)
                else ([str(x) for x in li_classes_val] if isinstance(li_classes_val, list) else [])
            )
            li_id = str(li.get("id", "")).strip()
            meta["tag"] = "li"
            if li_classes:
                meta["classes"] = li_classes
            if li_id:
                meta["id"] = li_id
            meta["is_list"] = True
            meta["list_depth"] = depth
            meta["list_type"] = list_type
            yield ("li", text, meta)

        for n in nested:
            n_type = n.name.lower()
            for inner_li in n.find_all("li", recursive=False):
                yield from self._extract_li(inner_li, depth + 1, n_type, context)

    def _extract_flow(
        self, container: Tag, context: dict[str, Any]
    ) -> Iterator[tuple[str, str, dict[str, Any]]]:
        """Extract semantic text blocks and tables in visual document reading order.

        Preserves:
        - Direct text inside blockquotes before/after/between nested block tags.
        - Nested blockquote depth and parent semantics without duplication.
        - Nested lists (direct text on parent <li>, sub-items on child <li>).
        - HTML tables (rows, cells, empty cells, and surrounding paragraph order).
        """
        inline_buffer: list[Any] = []

        def flush_inline() -> Iterator[tuple[str, str, dict[str, Any]]]:
            nonlocal inline_buffer
            if not inline_buffer:
                return
            text = "".join(
                str(c) if isinstance(c, NavigableString) else c.get_text() for c in inline_buffer
            ).strip()
            inline_buffer = []
            if not text:
                return
            meta = dict(context)
            tag = meta.get("tag", "blockquote" if context.get("is_quote") else "p")
            meta["tag"] = tag
            yield (tag, text, meta)

        for child in container.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                inline_buffer.append(child)
            elif isinstance(child, Tag):
                t_name = child.name.lower()

                if t_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    yield from flush_inline()
                    text = child.get_text().strip()
                    if text:
                        meta = dict(context)
                        self._populate_elem_meta(child, meta, t_name)
                        meta["heading_level"] = int(t_name[1])
                        yield (t_name, text, meta)

                elif t_name == "p":
                    yield from flush_inline()
                    text = child.get_text().strip()
                    if text:
                        meta = dict(context)
                        self._populate_elem_meta(child, meta, "p")
                        yield ("p", text, meta)

                elif t_name == "blockquote":
                    yield from flush_inline()
                    bq_ctx = dict(context)
                    self._populate_elem_meta(child, bq_ctx, "blockquote")
                    bq_ctx["is_quote"] = True
                    bq_ctx["parent_tag"] = "blockquote"
                    bq_ctx["quote_depth"] = bq_ctx.get("quote_depth", 0) + 1
                    bq_classes = bq_ctx.get("classes")
                    if bq_classes:
                        bq_ctx["parent_classes"] = bq_classes
                    yield from self._extract_flow(child, bq_ctx)

                elif t_name in ["ul", "ol"]:
                    yield from flush_inline()
                    for li in child.find_all("li", recursive=False):
                        yield from self._extract_li(li, 1, t_name, context)

                elif t_name == "table":
                    yield from flush_inline()
                    table_id = str(uuid4())
                    rows = [tr for tr in child.find_all("tr") if tr.find_parent("table") == child]
                    total_rows = len(rows)
                    for r_idx, row in enumerate(rows):
                        cells = [
                            c for c in row.find_all(["th", "td"]) if c.find_parent("tr") == row
                        ]
                        # Preserve all cells in order, preserving empty cells as empty strings
                        cell_texts = [c.get_text(separator="\n").strip() for c in cells]
                        row_str = " | ".join(cell_texts)
                        tbl_meta = dict(context)
                        self._populate_elem_meta(child, tbl_meta, "table")
                        tbl_meta["tag"] = "table"
                        tbl_meta["style_name"] = "Table"
                        tbl_meta["is_table_row"] = True
                        tbl_meta["table_id"] = table_id
                        tbl_meta["row_index"] = r_idx
                        tbl_meta["total_rows"] = total_rows
                        tbl_meta["cells_count"] = len(cell_texts)
                        tbl_meta["cells"] = cell_texts
                        is_header = any(c.name == "th" for c in cells) or (
                            row.find_parent("thead") is not None
                        )
                        tbl_meta["is_header_row"] = bool(is_header)
                        yield ("table", row_str, tbl_meta)

                elif t_name in ["div", "section", "article", "main", "header", "footer"]:
                    yield from flush_inline()
                    div_ctx = dict(context)
                    div_classes = child.get("class")
                    if div_classes:
                        div_ctx["container_classes"] = (
                            div_classes if isinstance(div_classes, list) else div_classes.split()
                        )
                    yield from self._extract_flow(child, div_ctx)

                else:
                    # Inline element: span, em, strong, a, etc.
                    inline_buffer.append(child)

        yield from flush_inline()

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

        chapters: list[Chapter] = []
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

            # Process elements preserving visual reading order and flow
            for tag_name, text, elem_meta in self._extract_flow(body, {}):
                total_chars += len(text)

                # Chapter Heading: <h1>
                if tag_name == "h1":
                    # If an empty placeholder chapter was created, update its title
                    has_content = current_chapter is not None and any(
                        b.type != BlockType.HEADING
                        for s in current_chapter.sections
                        for b in s.blocks
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
                        metadata=dict(elem_meta),
                    )
                    seq_idx += 1
                    current_section = Section(
                        section_index=section_idx, heading=text, blocks=[heading_block]
                    )
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
                        metadata=dict(elem_meta),
                    )
                    seq_idx += 1
                    current_section = Section(
                        section_index=section_idx, heading=text, blocks=[subheading_block]
                    )
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

                b_type = (
                    BlockType.QUOTE
                    if (tag_name == "blockquote" or elem_meta.get("is_quote"))
                    else BlockType.PARAGRAPH
                )
                current_section.blocks.append(
                    Block(
                        type=b_type,
                        source_text=text,
                        state=BlockState.INGESTED,
                        sequence_index=seq_idx,
                        metadata=dict(elem_meta),
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
