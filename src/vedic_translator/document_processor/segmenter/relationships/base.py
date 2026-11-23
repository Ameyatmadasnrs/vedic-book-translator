"""Base interfaces and configuration profiles for block relationship resolution."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from vedic_translator.core.models import Section, VerseUnit


class RelationshipProfile(BaseModel):
    """Configurable profile defining book-specific structural patterns, weights, and thresholds."""

    name: str = "generic_profile"

    # Regex patterns for identifying verse numbers, anchors, and metrical markers
    verse_number_patterns: list[str] = Field(default_factory=list)
    metrical_marker_patterns: dict[str, str] = Field(default_factory=dict)
    translation_anchor_patterns: list[str] = Field(default_factory=list)
    composite_translation_patterns: list[str] = Field(default_factory=list)
    footnote_anchor_patterns: list[str] = Field(default_factory=list)

    # Configurable confidence weights (sum to 1.0)
    weight_anchor_match: float = 0.40
    weight_sequence_flow: float = 0.30
    weight_spatial_proximity: float = 0.20
    weight_script_consistency: float = 0.10

    # Configurable threshold gates (provisional structural heuristics)
    threshold_auto_accept: float = 0.85
    threshold_ambiguous: float = 0.60

    # Operational settings
    enable_contiguity_grouping: bool = True
    allow_unanchored_verses: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class IRelationshipResolver(ABC):
    """Abstract Port for resolving semantic relationships between classified blocks."""

    @abstractmethod
    def resolve_relationships(
        self,
        section: Section,
        profile: RelationshipProfile | None = None,
    ) -> list[VerseUnit]:
        """Resolve relationships for blocks within a section, returning VerseUnits."""
        pass
