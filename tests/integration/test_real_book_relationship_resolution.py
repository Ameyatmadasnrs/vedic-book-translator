"""Integration test verifying relationship resolution on real Ramcharit Manas PDF pages."""

import json
from pathlib import Path

import pytest

from vedic_translator.core.models import (
    Chapter,
    Document,
    DocumentStatus,
    RoutingAction,
    Section,
    VerseUnitType,
)
from vedic_translator.document_processor.extractors.pdf import PDFExtractor
from vedic_translator.document_processor.segmenter.pipeline import SegmenterPipeline
from vedic_translator.document_processor.segmenter.relationships.profiles import (
    RAMCHARITA_MANAS_PROFILE,
)
from vedic_translator.document_processor.segmenter.validator import (
    DocumentIntegrityValidator,
)

REAL_BOOK_PATH = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")


@pytest.fixture(scope="module")
def extracted_full_doc():
    """Extract document once for integration tests."""
    extractor = PDFExtractor()
    return extractor.extract(REAL_BOOK_PATH)


@pytest.mark.skipif(
    not REAL_BOOK_PATH.exists(), reason="Test book PDF not found in data/test_books/"
)
class TestRealBookRelationshipResolution:
    """Integration test suite executing relationship resolution against Ramcharit Manas."""

    def test_pages_215_to_220_resolution(self, extracted_full_doc) -> None:
        """Verify relationship resolution on Pages 215-220 (Doha 188 & early Chaupais)."""
        target_pages = set(range(215, 221))
        sample_blocks = [
            b
            for ch in extracted_full_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") in target_pages
        ]
        assert len(sample_blocks) >= 20

        # Construct test sub-document preserving original block identities
        sub_doc = Document(
            metadata=extracted_full_doc.metadata,
            chapters=[
                Chapter(
                    chapter_index=1,
                    title="Bala Kanda Sample",
                    sections=[Section(section_index=1, blocks=sample_blocks)],
                )
            ],
            status=DocumentStatus.INGESTED,
        )

        pipeline = SegmenterPipeline(relationship_profile=RAMCHARITA_MANAS_PROFILE)
        enriched_doc = pipeline.segment(sub_doc)

        sec = enriched_doc.chapters[0].sections[0]
        assert len(sec.verse_units) >= 5

        # Check types include Doha and Chaupai
        unit_types = {vu.unit_type for vu in sec.verse_units}
        assert VerseUnitType.DOHA in unit_types or VerseUnitType.CHAUPAI in unit_types

        # Check contiguity grouping was triggered for multi-line verses
        grouped_units = [vu for vu in sec.verse_units if len(vu.original_script_block_ids) > 1]
        assert len(grouped_units) >= 1
        assert "contiguity_grouping" in grouped_units[0].confidence.provenance_rules

        # Check DocumentIntegrityValidator passes
        validator = DocumentIntegrityValidator(raise_on_error=True)
        report = validator.validate(enriched_doc)
        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_pages_11_to_15_mantra_and_prayer_resolution(self, extracted_full_doc) -> None:
        """Verify relationship resolution on invocation pages 11-15."""
        target_pages = set(range(11, 16))
        sample_blocks = [
            b
            for ch in extracted_full_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") in target_pages
        ]
        assert len(sample_blocks) >= 15

        sub_doc = Document(
            metadata=extracted_full_doc.metadata,
            chapters=[
                Chapter(
                    chapter_index=1,
                    title="Invocations",
                    sections=[Section(section_index=1, blocks=sample_blocks)],
                )
            ],
        )

        pipeline = SegmenterPipeline(relationship_profile=RAMCHARITA_MANAS_PROFILE)
        enriched_doc = pipeline.segment(sub_doc)

        validator = DocumentIntegrityValidator(raise_on_error=True)
        report = validator.validate(enriched_doc)
        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_editorial_review_export_format(self, extracted_full_doc, tmp_path) -> None:
        """Verify that ambiguous or flagged verse units export cleanly to review JSON."""
        target_pages = {11, 12, 215, 216}
        sample_blocks = [
            b
            for ch in extracted_full_doc.chapters
            for s in ch.sections
            for b in s.blocks
            if b.metadata.get("page") in target_pages
        ]

        sub_doc = Document(
            metadata=extracted_full_doc.metadata,
            chapters=[
                Chapter(
                    chapter_index=1,
                    title="Bala Kanda",
                    sections=[Section(section_index=1, blocks=sample_blocks)],
                )
            ],
        )

        pipeline = SegmenterPipeline(relationship_profile=RAMCHARITA_MANAS_PROFILE)
        enriched_doc = pipeline.segment(sub_doc)

        # Collect flagged / ambiguous units
        ambiguous_units = [
            vu
            for ch in enriched_doc.chapters
            for s in ch.sections
            for vu in s.verse_units
            if vu.confidence.routing_action != RoutingAction.AUTO_ACCEPTED
        ]

        assert len(ambiguous_units) > 0

        # Export to JSON
        export_file = tmp_path / "editorial_review_test.json"
        export_data = [vu.model_dump(mode="json") for vu in ambiguous_units]
        export_file.write_text(
            json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        assert export_file.exists()
        loaded = json.loads(export_file.read_text(encoding="utf-8"))
        assert len(loaded) == len(ambiguous_units)
        assert loaded[0]["confidence"]["routing_action"] in ("AMBIGUOUS", "FLAGGED_FOR_REVIEW")
        assert "provenance_rules" in loaded[0]["confidence"]
        assert "evidence" in loaded[0]["confidence"]
