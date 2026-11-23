"""Deterministic ContentClassifier for universal English document structures."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from vedic_translator.core.models import (
    AlternativeClassification,
    Block,
    BlockType,
    ClassificationProvenance,
    utc_now,
)
from vedic_translator.document_processor.segmenter.base import SegmentationProfile


class BlockContext(BaseModel):
    """Contextual neighbor information for block classification."""

    preceding_block: Block | None = None
    following_block: Block | None = None
    section_heading: str | None = None
    block_index_in_section: int = 0
    total_blocks_in_section: int = 1


class BlockClassification(BaseModel):
    """Result of content classification for a single block."""

    block_type: BlockType
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: ClassificationProvenance
    alternatives: list[AlternativeClassification] = Field(default_factory=list)


# Precompiled regular expressions for universal English patterns
THEMATIC_BREAK_REGEX = re.compile(r"^(?:[\*\-_•—–]\s*){3,}$", re.UNICODE)
FOOTNOTE_ANCHOR_REGEX = re.compile(r"^(?:\[\^?\d+\]|\[\d+\]|\(\d+\)|\*+|\†|\‡)\s+\S+", re.UNICODE)
LIST_BULLET_REGEX = re.compile(r"^[-*•◦▪⁃+–—]\s+\S+", re.UNICODE)
LIST_NUMBERED_REGEX = re.compile(
    r"^(?:(?:\d+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)[\.\)]|\((?:\d+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)\))\s+\S+",
    re.UNICODE,
)
CAPTION_REGEX = re.compile(
    r"^(?:Figure|Fig\.|Table|Illustration|Plate|Diagram)\s+\d+[:.\s\-–—]",
    re.IGNORECASE | re.UNICODE,
)
MARKDOWN_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(\S.*)$")
MARKDOWN_QUOTE_REGEX = re.compile(r"^>\s*(\S.*)$")
COMMON_ENGLISH_FINITE_VERBS = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "does",
    "do",
    "did",
    "explains",
    "stated",
    "says",
    "wrote",
    "argued",
    "means",
    "refers",
    "becomes",
    "remains",
    "seems",
    "appears",
}


def clamp_confidence(val: float) -> float:
    """Clamp confidence score strictly to [0.0, 1.0]."""
    return max(0.0, min(1.0, round(val, 4)))


class ContentClassifier:
    """Deterministic classifier for universal document structures in ordinary English books."""

    def __init__(
        self,
        profile: SegmentationProfile | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.profile = profile or SegmentationProfile()
        self.clock = clock or utc_now

    def classify(self, block: Block, context: BlockContext | None = None) -> BlockClassification:
        """Classify a block using deterministic formatting, geometry, patterns, and neighbors."""
        text = block.source_text.strip()
        meta = block.metadata

        candidates: list[tuple[BlockType, float, str, str]] = []

        # 1. Evaluate THEMATIC_BREAK
        break_match = self._check_thematic_break(text, meta)
        if break_match:
            candidates.append(break_match)

        # 2. Evaluate FOOTNOTE
        footnote_match = self._check_footnote(text, meta, context)
        if footnote_match:
            candidates.append(footnote_match)

        # 3. Evaluate TABLE
        table_match = self._check_table(text, meta)
        if table_match:
            candidates.append(table_match)

        # 4. Evaluate CAPTION
        caption_match = self._check_caption(text, meta)
        if caption_match:
            candidates.append(caption_match)

        # 5. Evaluate LIST_ITEM
        list_match = self._check_list_item(text, meta)
        if list_match:
            candidates.append(list_match)

        # 6. Evaluate HEADING / SUBHEADING
        heading_matches = self._check_headings(text, meta, context)
        candidates.extend(heading_matches)

        # 7. Evaluate EPIGRAPH
        epigraph_match = self._check_epigraph(text, meta, context)
        if epigraph_match:
            candidates.append(epigraph_match)

        # 8. Evaluate BLOCKQUOTE / QUOTE
        quote_match = self._check_blockquote(text, meta, context)
        if quote_match:
            candidates.append(quote_match)

        # 9. Evaluate PARAGRAPH (standard universal prose)
        paragraph_match = self._check_paragraph(text, meta)
        candidates.append(paragraph_match)

        # Sort candidates deterministically by confidence (descending) and priority order
        sorted_candidates = self._sort_candidates(candidates)
        winner_type, winner_conf, winner_method, winner_rule = sorted_candidates[0]

        # Assemble alternative hypotheses
        alternatives: list[AlternativeClassification] = []
        for alt_type, alt_conf, _, alt_rule in sorted_candidates[1:4]:
            if alt_conf > 0.30 and alt_type != winner_type:
                alternatives.append(
                    AlternativeClassification(
                        suggested_type=alt_type,
                        confidence=alt_conf,
                        rule_name=alt_rule,
                        reason=f"Secondary candidate with score {alt_conf:.2f}",
                    )
                )

        provenance = ClassificationProvenance(
            method=winner_method,
            rule_name=winner_rule,
            confidence=winner_conf,
            alternatives=alternatives,
            applied_at=self.clock(),
        )

        return BlockClassification(
            block_type=winner_type,
            confidence=winner_conf,
            provenance=provenance,
            alternatives=alternatives,
        )

    def _sort_candidates(
        self, candidates: list[tuple[BlockType, float, str, str]]
    ) -> list[tuple[BlockType, float, str, str]]:
        """Sort candidates deterministically by score and priority hierarchy."""
        priority_map = {name: i for i, name in enumerate(self.profile.priority_order)}

        def sort_key(item: tuple[BlockType, float, str, str]) -> tuple[float, int, str]:
            b_type, conf, _, rule = item
            # primary: confidence descending (-conf)
            # secondary: priority rank ascending
            # tertiary: rule name ascending (deterministic stability)
            rank = priority_map.get(b_type.value, 999)
            return (-round(conf, 4), rank, rule)

        return sorted(candidates, key=sort_key)

    # -------------------------------------------------------------------------
    # Individual Universal Content Rule Checkers
    # -------------------------------------------------------------------------

    def _check_thematic_break(
        self, text: str, meta: dict[str, Any]
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for scene dividers, asterisks, or horizontal rules."""
        if len(text) > self.profile.thematic_break_max_chars:
            return None

        # Format native clues
        if meta.get("tag") == "hr" or meta.get("style_name") in ["Horizontal Line", "Divider"]:
            return (
                BlockType.THEMATIC_BREAK,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "native_divider",
            )

        if THEMATIC_BREAK_REGEX.match(text):
            # Check there are no alphabetical words
            if not re.search(r"[a-zA-Zа-яА-Я\d]", text):
                return (
                    BlockType.THEMATIC_BREAK,
                    clamp_confidence(self.profile.syntax_pattern_weight + 0.07),
                    "heuristic_rule",
                    "regex_thematic_break",
                )
        return None

    def _check_footnote(
        self, text: str, meta: dict[str, Any], context: BlockContext | None
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for footnote or endnote definitions."""
        # 1. Format native (DOCX style or EPUB semantic aside/class)
        style = str(meta.get("style_name", "")).lower()
        if "footnote" in style or "endnote" in style:
            return (
                BlockType.FOOTNOTE,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "docx_footnote_style",
            )

        tag = meta.get("tag")
        classes = [str(c).lower() for c in meta.get("classes", [])]
        if tag == "aside" or any("footnote" in c for c in classes):
            return (
                BlockType.FOOTNOTE,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "epub_footnote_tag",
            )

        # 2. PDF layout geometry: at page bottom with small font
        bbox = meta.get("bbox")
        font_size = meta.get("font_size", 0.0)
        if bbox and len(bbox) == 4:
            y1 = bbox[3]
            # y1 > 710pt on standard 792pt page indicates bottom footer region
            if y1 > 710.0 and (font_size > 0 and font_size <= 9.5):
                return (
                    BlockType.FOOTNOTE,
                    clamp_confidence(self.profile.format_native_weight - 0.02),
                    "layout_geometry",
                    "pdf_bottom_footer_region",
                )

        # 3. Textual footnote pattern: starts with [^1] or (1)
        if FOOTNOTE_ANCHOR_REGEX.match(text):
            # Contextual reinforcement: if it's towards the end of section/page
            conf = self.profile.syntax_pattern_weight
            if context and context.block_index_in_section >= (context.total_blocks_in_section - 2):
                conf += 0.05
            return (
                BlockType.FOOTNOTE,
                clamp_confidence(conf),
                "heuristic_rule",
                "regex_footnote_anchor",
            )

        return None

    def _check_table(
        self, text: str, meta: dict[str, Any]
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for tabular data or table rows."""
        # Format native
        if meta.get("tag") in ["table", "tr", "td", "th"] or meta.get("style_name") in [
            "Table",
            "Table Grid",
        ]:
            return (
                BlockType.TABLE,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "native_table_tag",
            )

        # Markdown table pattern (| Col 1 | Col 2 |)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2 and all(
            line.startswith("|") and line.endswith("|") and line.count("|") >= 2 for line in lines
        ):
            return (
                BlockType.TABLE,
                clamp_confidence(self.profile.syntax_pattern_weight + 0.05),
                "heuristic_rule",
                "markdown_table_syntax",
            )

        # Tab-separated columnar text
        if len(lines) >= 2 and all(line.count("\t") >= 2 for line in lines):
            return (
                BlockType.TABLE,
                clamp_confidence(self.profile.syntax_pattern_weight + 0.04),
                "heuristic_rule",
                "tab_delimited_table",
            )

        return None

    def _check_caption(
        self, text: str, meta: dict[str, Any]
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for figure, illustration, or table captions."""
        style = str(meta.get("style_name", "")).lower()
        if "caption" in style or meta.get("tag") in ["figcaption", "caption"]:
            return (
                BlockType.CAPTION,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "native_caption_style",
            )

        if CAPTION_REGEX.match(text) and len(text.splitlines()) <= 3:
            return (
                BlockType.CAPTION,
                clamp_confidence(self.profile.syntax_pattern_weight + 0.05),
                "heuristic_rule",
                "regex_caption_prefix",
            )

        return None

    def _check_list_item(
        self, text: str, meta: dict[str, Any]
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for bulleted, numbered, or lettered list items."""
        style = str(meta.get("style_name", "")).lower()
        if (
            "list" in style
            or "bullet" in style
            or meta.get("numPr") is not None
            or meta.get("is_list")
        ):
            return (
                BlockType.LIST_ITEM,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "docx_list_style",
            )

        if meta.get("tag") in ["li", "dt", "dd"] or meta.get("is_list"):
            return (
                BlockType.LIST_ITEM,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "epub_li_tag",
            )

        # Bullet list regex
        if LIST_BULLET_REGEX.match(text):
            return (
                BlockType.LIST_ITEM,
                clamp_confidence(self.profile.syntax_pattern_weight + 0.04),
                "heuristic_rule",
                "regex_bullet_prefix",
            )

        # Numbered list regex
        if LIST_NUMBERED_REGEX.match(text) and len(text.splitlines()) <= 4:
            return (
                BlockType.LIST_ITEM,
                clamp_confidence(self.profile.syntax_pattern_weight),
                "heuristic_rule",
                "regex_numbered_prefix",
            )

        return None

    def _check_headings(
        self, text: str, meta: dict[str, Any], context: BlockContext | None
    ) -> list[tuple[BlockType, float, str, str]]:
        """Check for HEADING (H1/major) or SUBHEADING (H2-H6/minor)."""
        results: list[tuple[BlockType, float, str, str]] = []
        words = text.split()
        word_count = len(words)

        # 1. Format Native: DOCX Style
        style = str(meta.get("style_name", ""))
        if style:
            s_lower = style.lower()
            if s_lower in ["heading 1", "title", "chapter title"]:
                results.append(
                    (
                        BlockType.HEADING,
                        clamp_confidence(self.profile.format_native_weight),
                        "format_native",
                        "docx_heading1_style",
                    )
                )
                return results
            if any(s_lower == f"heading {lvl}" for lvl in range(2, 7)) or "subtitle" in s_lower:
                results.append(
                    (
                        BlockType.SUBHEADING,
                        clamp_confidence(self.profile.format_native_weight),
                        "format_native",
                        "docx_subheading_style",
                    )
                )
                return results

        # 2. Format Native: EPUB tags or heading_level
        tag = meta.get("tag")
        heading_level = meta.get("heading_level")
        if tag == "h1" or heading_level == 1:
            results.append(
                (
                    BlockType.HEADING,
                    clamp_confidence(self.profile.format_native_weight),
                    "format_native",
                    f"epub_{tag or 'h1'}_tag",
                )
            )
            return results
        if tag in ["h2", "h3", "h4", "h5", "h6"] or (
            isinstance(heading_level, int) and heading_level > 1
        ):
            results.append(
                (
                    BlockType.SUBHEADING,
                    clamp_confidence(self.profile.format_native_weight),
                    "format_native",
                    f"epub_{tag or f'h{heading_level}'}_tag",
                )
            )
            return results

        # 3. Format Native: Markdown hashes in text
        md_match = MARKDOWN_HEADING_REGEX.match(text)
        if md_match:
            hashes = len(md_match.group(1))
            h_type = BlockType.HEADING if hashes <= 2 else BlockType.SUBHEADING
            results.append(
                (
                    h_type,
                    clamp_confidence(self.profile.syntax_pattern_weight + 0.05),
                    "heuristic_rule",
                    f"markdown_h{hashes}",
                )
            )
            return results

        # 4. Text Pattern: Short title with no terminal period (at most 2 lines)
        if (
            1 <= word_count <= self.profile.heading_max_words
            and len(text) <= self.profile.heading_max_chars
            and not text.endswith((".", ";", ":"))
            and len(text.splitlines()) <= 2
        ):
            # Check for Chapter/Part label
            if re.match(
                r"^(?:Chapter|Part|Section|Canto|Book|Volume|Глава|Часть)\s+([IVXLCDM\d]+)",
                text,
                re.IGNORECASE,
            ):
                results.append(
                    (
                        BlockType.HEADING,
                        clamp_confidence(self.profile.syntax_pattern_weight + 0.06),
                        "heuristic_rule",
                        "regex_chapter_prefix",
                    )
                )
                return results

            # All caps or title case check
            is_all_caps = text.isupper() and len(text) > 3
            is_title_case = text.istitle()

            # Configurable prose veto: if sentence contains multiple verbs and is long, veto heading
            has_multiple_verbs = self._count_finite_verbs(words) >= 2
            if not (self.profile.enable_prose_veto and has_multiple_verbs):
                if is_all_caps or is_title_case:
                    # PDF font size clue
                    font_size = meta.get("font_size", 0.0)
                    conf = self.profile.syntax_pattern_weight - 0.05
                    if font_size >= 14.0:
                        conf += 0.10
                        results.append(
                            (
                                BlockType.HEADING,
                                clamp_confidence(conf),
                                "layout_geometry",
                                "font_size_heading",
                            )
                        )
                    elif font_size >= 12.0:
                        conf += 0.05
                        results.append(
                            (
                                BlockType.SUBHEADING,
                                clamp_confidence(conf),
                                "layout_geometry",
                                "font_size_subheading",
                            )
                        )
                    else:
                        results.append(
                            (
                                BlockType.SUBHEADING,
                                clamp_confidence(conf),
                                "heuristic_rule",
                                "capitalized_short_title",
                            )
                        )

        return results

    def _check_epigraph(
        self, text: str, meta: dict[str, Any], context: BlockContext | None
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for opening chapter epigraph/motto."""
        if not context:
            return None

        # Epigraphs appear at the very beginning of a chapter/section (index 0 or 1, right after heading)
        prec = context.preceding_block
        is_after_heading = (
            prec is not None
            and prec.type in [BlockType.HEADING, BlockType.SUBHEADING]
            or context.block_index_in_section <= 1
        )
        if not is_after_heading:
            return None

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > self.profile.epigraph_max_lines or len(text) > 350:
            return None

        # Explicit format style
        style = str(meta.get("style_name", "")).lower()
        if "epigraph" in style:
            return (
                BlockType.EPIGRAPH,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "docx_epigraph_style",
            )

        # Contextual heuristic: ends with author attribution line (e.g. — Ralph Waldo Emerson)
        has_attribution = any(re.match(r"^[-—–]\s+[A-ZА-Я]", line) for line in lines)
        is_quoted = (
            text.startswith(('"', "“", "«")) and text.endswith(('"', "”", "»")) or has_attribution
        )

        if is_quoted:
            conf = self.profile.syntax_pattern_weight + 0.04  # 0.92 beats generic blockquote (0.88)
            return (
                BlockType.EPIGRAPH,
                clamp_confidence(conf),
                "heuristic_rule",
                "epigraph_after_heading_with_attribution",
            )

        return None

    def _check_blockquote(
        self, text: str, meta: dict[str, Any], context: BlockContext | None
    ) -> tuple[BlockType, float, str, str] | None:
        """Check for blockquotes, indented quotations, or citations."""
        # 1. Format Native (DOCX style or EPUB tag)
        style = str(meta.get("style_name", "")).lower()
        if "quote" in style or "blockquote" in style:
            return (
                BlockType.BLOCKQUOTE,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "docx_quote_style",
            )

        if (
            meta.get("tag") == "blockquote"
            or meta.get("is_quote")
            or meta.get("parent_tag") == "blockquote"
        ):
            return (
                BlockType.BLOCKQUOTE,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "epub_blockquote_tag",
            )

        # 2. Markdown quote marker: > Quote text
        if MARKDOWN_QUOTE_REGEX.match(text):
            return (
                BlockType.BLOCKQUOTE,
                clamp_confidence(self.profile.syntax_pattern_weight + 0.05),
                "heuristic_rule",
                "markdown_quote_prefix",
            )

        # 3. PDF Indentation geometry (indented substantially more than normal body text)
        bbox = meta.get("bbox")
        if bbox and len(bbox) == 4:
            x0 = bbox[0]
            # Standard left margin in published PDFs is typically 50-54pt.
            # An indentation >= 72pt (1 inch) indicates blockquote
            if x0 >= 72.0:
                conf = self.profile.layout_geometry_weight
                return (
                    BlockType.BLOCKQUOTE,
                    clamp_confidence(conf),
                    "layout_geometry",
                    "pdf_indented_margin",
                )

        # 4. Text quotation marks spanning complete block with attribution line
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        has_attribution = any(re.match(r"^[-—–]\s+[A-ZА-Я]", line) for line in lines)
        if has_attribution and len(lines) >= 2:
            return (
                BlockType.BLOCKQUOTE,
                clamp_confidence(self.profile.syntax_pattern_weight),
                "heuristic_rule",
                "prose_with_author_attribution",
            )

        return None

    def _check_paragraph(
        self, text: str, meta: dict[str, Any]
    ) -> tuple[BlockType, float, str, str]:
        """Check for standard universal narrative prose paragraph."""
        style = str(meta.get("style_name", "")).lower()
        if style in ["normal", "body text", "paragraph"]:
            return (
                BlockType.PARAGRAPH,
                clamp_confidence(self.profile.format_native_weight),
                "format_native",
                "docx_body_style",
            )

        # Positive body prose heuristics: complete sentences with terminal punctuation
        word_count = len(text.split())
        has_terminal_punct = text.endswith((".", "!", "?", ".”", '."'))

        conf = self.profile.fallback_paragraph_weight
        if word_count >= 10 and has_terminal_punct:
            conf += 0.20  # Reaches 0.90 for standard complete prose sentences
        elif word_count >= 5:
            conf += 0.10

        return (
            BlockType.PARAGRAPH,
            clamp_confidence(conf),
            "heuristic_rule",
            "prose_body_sentence",
        )

    def _count_finite_verbs(self, words: list[str]) -> int:
        """Count common finite grammatical verbs in word tokens."""
        clean_words = {re.sub(r"[^\w]", "", w.lower()) for w in words}
        return len(clean_words.intersection(COMMON_ENGLISH_FINITE_VERBS))
