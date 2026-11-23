"""Base interfaces and configuration profiles for document semantic segmentation."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from vedic_translator.core.models import Document


class SegmentationProfile(BaseModel):
    """Configuration parameters and evidence weights for deterministic segmentation."""

    name: str = "default_universal"

    # Heading thresholds
    heading_max_words: int = 15
    heading_max_chars: int = 120

    # Epigraph & Quote thresholds
    epigraph_max_lines: int = 6
    quote_min_indent_pt: float = 20.0

    # Thematic break thresholds
    thematic_break_max_chars: int = 30

    # Configurable prose-veto behavior (NOT an unconditional hardcoded rule)
    enable_prose_veto: bool = True
    prose_veto_min_words: int = 12
    prose_veto_min_finite_verbs: int = 2

    # Deterministic evidence weights
    format_native_weight: float = 0.95
    syntax_pattern_weight: float = 0.88
    layout_geometry_weight: float = 0.82
    context_neighbor_weight: float = 0.75
    fallback_paragraph_weight: float = 0.70

    # Tie-breaking priority list (highest priority first)
    priority_order: list[str] = Field(
        default_factory=lambda: [
            "THEMATIC_BREAK",
            "TABLE",
            "FOOTNOTE",
            "CAPTION",
            "LIST_ITEM",
            "HEADING",
            "SUBHEADING",
            "EPIGRAPH",
            "BLOCKQUOTE",
            "QUOTE",
            "PARAGRAPH",
        ]
    )


class ISegmenter(ABC):
    """Abstract Port for document semantic segmentation."""

    @abstractmethod
    def segment(self, document: Document) -> Document:
        """Process a raw Document AST and return an enriched Document AST."""
        pass
