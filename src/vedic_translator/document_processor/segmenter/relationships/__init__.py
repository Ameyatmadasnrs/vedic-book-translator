"""Relationship resolution package for semantic block structuring."""

from vedic_translator.document_processor.segmenter.relationships.base import (
    IRelationshipResolver,
    RelationshipProfile,
)
from vedic_translator.document_processor.segmenter.relationships.profiles import (
    RAMCHARITA_MANAS_PROFILE,
    STANDARD_PROSE_PROFILE,
    create_ramcharita_manas_profile,
    create_standard_prose_profile,
)
from vedic_translator.document_processor.segmenter.relationships.resolver import (
    RuleBasedRelationshipResolver,
)

__all__ = [
    "IRelationshipResolver",
    "RelationshipProfile",
    "RuleBasedRelationshipResolver",
    "create_ramcharita_manas_profile",
    "create_standard_prose_profile",
    "RAMCHARITA_MANAS_PROFILE",
    "STANDARD_PROSE_PROFILE",
]
