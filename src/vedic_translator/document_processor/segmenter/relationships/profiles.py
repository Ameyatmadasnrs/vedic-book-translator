"""Concrete relationship profiles for specialized literary traditions."""

from vedic_translator.core.models import VerseUnitType
from vedic_translator.document_processor.segmenter.relationships.base import RelationshipProfile


def create_ramcharita_manas_profile() -> RelationshipProfile:
    """Create a RelationshipProfile configured for Gita Press Ramcharit Manas.

    Encapsulates Awadhi Chaupai/Doha meter prefixes, danda numbering conventions,
    and composite English translation anchors.
    """
    return RelationshipProfile(
        name="ramcharita_manas_gita_press",
        verse_number_patterns=[
            r"॥\s*(\d+)\s*॥",
            r"॥\s*(\d+)\s*\(([क-ह])\)\s*॥",
            r"\|\s*(\d+)\s*\|",
            r"\|\s*(\d+)\s*\(([क-ह])\)\s*\|",
            r"\b(?:Do\.|So\.|Cau\.|Chh\.|Sloka:)\s*(\d+)",
        ],
        metrical_marker_patterns={
            # Standard normalized Gita Press forms (Devanagari abbreviation + em-dash)
            "दो०—": VerseUnitType.DOHA.value,
            "चौ०—": VerseUnitType.CHAUPAI.value,
            "सो०—": VerseUnitType.SORATHA.value,
            "छं०—": VerseUnitType.CHHANDA.value,
            # Hyphen and alternate dash variants
            "दो०-": VerseUnitType.DOHA.value,
            "चौ०-": VerseUnitType.CHAUPAI.value,
            "सो०-": VerseUnitType.SORATHA.value,
            "छं०-": VerseUnitType.CHHANDA.value,
            "दो0—": VerseUnitType.DOHA.value,
            "चौ0—": VerseUnitType.CHAUPAI.value,
            "सो0—": VerseUnitType.SORATHA.value,
            "छं0—": VerseUnitType.CHHANDA.value,
            # Legacy font conversion artifacts (preserved for backward compatibility)
            "दो0ó": VerseUnitType.DOHA.value,
            "चौ0ó": VerseUnitType.CHAUPAI.value,
            "सो0ó": VerseUnitType.SORATHA.value,
            "छं0ó": VerseUnitType.CHHANDA.value,
            # Bare abbreviations without trailing dash
            "दो०": VerseUnitType.DOHA.value,
            "चौ०": VerseUnitType.CHAUPAI.value,
            "सो०": VerseUnitType.SORATHA.value,
            "छं०": VerseUnitType.CHHANDA.value,
            # Traditional full name headings
            "श्लोक": VerseUnitType.SLOKA.value,
            "दोहा": VerseUnitType.DOHA.value,
            "चौपाई": VerseUnitType.CHAUPAI.value,
            "सोरठा": VerseUnitType.SORATHA.value,
            "छन्द": VerseUnitType.CHHANDA.value,
            # IAST metrical markers
            "Do.:": VerseUnitType.DOHA.value,
            "Cau.:": VerseUnitType.CHAUPAI.value,
            "So.:": VerseUnitType.SORATHA.value,
            "Chh.:": VerseUnitType.CHHANDA.value,
            "Sloka:": VerseUnitType.SLOKA.value,
            "Chaṁ.:": VerseUnitType.CHHANDA.value,
        },
        translation_anchor_patterns=[
            r"^\(([0-9]+(?:\s*[A-Z])?)\)",
            r"\(([0-9]+(?:\s*[A-Z])?)\)\s*$",
            r"^[“\"][A-Z]",
        ],
        composite_translation_patterns=[
            r"\(([0-9]+)\s*[-—–to]\s*([0-9]+)\)",
            r"\b(?:Chaupais?|Dohas?)\s*([0-9]+)\s*[-—–to]\s*([0-9]+)",
        ],
        footnote_anchor_patterns=[
            r"\[\^?(\d+)\]",
            r"\(([0-9]+)\)",
        ],
        threshold_auto_accept=0.85,
        threshold_ambiguous=0.60,
    )


def create_standard_prose_profile() -> RelationshipProfile:
    """Create a default RelationshipProfile for standard non-verse literature."""
    return RelationshipProfile(
        name="standard_prose",
        threshold_auto_accept=0.85,
        threshold_ambiguous=0.60,
        enable_contiguity_grouping=False,
        allow_unanchored_verses=False,
    )


# Default pre-instantiated profiles
RAMCHARITA_MANAS_PROFILE = create_ramcharita_manas_profile()
STANDARD_PROSE_PROFILE = create_standard_prose_profile()
