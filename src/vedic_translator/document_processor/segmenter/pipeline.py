"""SegmenterPipeline orchestrating deterministic segmentation and integrity validation."""

import copy
from collections.abc import Callable
from datetime import datetime

from loguru import logger

from vedic_translator.core.models import (
    Block,
    Chapter,
    Document,
    Section,
    utc_now,
)
from vedic_translator.document_processor.segmenter.base import (
    ISegmenter,
    SegmentationProfile,
)
from vedic_translator.document_processor.segmenter.classifier import (
    BlockContext,
    ContentClassifier,
)
from vedic_translator.document_processor.segmenter.relationships import (
    IRelationshipResolver,
    RelationshipProfile,
    RuleBasedRelationshipResolver,
)
from vedic_translator.document_processor.segmenter.validator import (
    DocumentIntegrityValidator,
)


class SegmenterPipeline(ISegmenter):
    """Pipeline coordinating deterministic content classification, AST enrichment, and validation."""

    def __init__(
        self,
        profile: SegmentationProfile | None = None,
        relationship_profile: RelationshipProfile | None = None,
        relationship_resolver: IRelationshipResolver | None = None,
        enable_relationship_resolution: bool = True,
        clock: Callable[[], datetime] | None = None,
        raise_on_integrity_error: bool = True,
    ) -> None:
        self.profile = profile or SegmentationProfile()
        self.relationship_profile = relationship_profile
        self.enable_relationship_resolution = enable_relationship_resolution
        self.relationship_resolver = (
            relationship_resolver
            if relationship_resolver is not None
            else RuleBasedRelationshipResolver()
        )
        self.clock = clock or utc_now
        self.classifier = ContentClassifier(profile=self.profile, clock=self.clock)
        self.validator = DocumentIntegrityValidator(raise_on_error=raise_on_integrity_error)

    def segment(self, document: Document) -> Document:
        """Non-destructively transform a raw Document AST into an enriched Document AST.

        Guarantees:
        - raw document is never mutated (deep-copy protection).
        - source_text, id, and sequence_index are preserved exactly.
        - enriched document passes all integrity invariants.
        """
        logger.info(f"Starting Stage 1 semantic segmentation on Document {document.id}")

        enriched_chapters: list[Chapter] = []

        for raw_chapter in document.chapters:
            enriched_sections: list[Section] = []

            for raw_section in raw_chapter.sections:
                raw_blocks = raw_section.blocks
                total_blocks = len(raw_blocks)
                enriched_blocks: list[Block] = []

                for idx, raw_block in enumerate(raw_blocks):
                    # Prepare contextual window for classification
                    prec_block = enriched_blocks[-1] if enriched_blocks else None
                    foll_block = raw_blocks[idx + 1] if idx + 1 < total_blocks else None

                    context = BlockContext(
                        preceding_block=prec_block,
                        following_block=foll_block,
                        section_heading=raw_section.heading,
                        block_index_in_section=idx,
                        total_blocks_in_section=total_blocks,
                    )

                    # 1. Deterministic classification
                    classification = self.classifier.classify(raw_block, context=context)

                    # 2. Deep-copy mutable metadata to guarantee immutability of raw AST
                    copied_metadata = copy.deepcopy(raw_block.metadata)

                    # 3. Construct enriched block with preserved identity and reading order
                    enriched_block = Block(
                        id=raw_block.id,
                        type=classification.block_type,
                        source_text=raw_block.source_text,  # Immutable string reference
                        target_text=raw_block.target_text,
                        state=raw_block.state,
                        verse_number=raw_block.verse_number,
                        sequence_index=raw_block.sequence_index,
                        history=copy.deepcopy(raw_block.history),
                        audit_result=copy.deepcopy(raw_block.audit_result),
                        metadata=copied_metadata,
                        provenance=classification.provenance,
                        alternative_classifications=classification.alternatives,
                        verse_unit_ids=copy.deepcopy(raw_block.verse_unit_ids),
                    )
                    enriched_blocks.append(enriched_block)

                enriched_section = Section(
                    id=raw_section.id,
                    section_index=raw_section.section_index,
                    heading=raw_section.heading,
                    verse_range=raw_section.verse_range,
                    blocks=enriched_blocks,
                    verse_units=[],
                    metadata=copy.deepcopy(raw_section.metadata),
                )

                # Stage B: Relationship Resolution (if enabled)
                if self.enable_relationship_resolution and self.relationship_resolver is not None:
                    verse_units = self.relationship_resolver.resolve_relationships(
                        section=enriched_section,
                        profile=self.relationship_profile,
                    )
                    enriched_section.verse_units = verse_units

                enriched_sections.append(enriched_section)

            enriched_chapter = Chapter(
                id=raw_chapter.id,
                chapter_index=raw_chapter.chapter_index,
                title=raw_chapter.title,
                sections=enriched_sections,
                summary=copy.deepcopy(raw_chapter.summary),
                metadata=copy.deepcopy(raw_chapter.metadata),
            )
            enriched_chapters.append(enriched_chapter)

        enriched_document = Document(
            id=document.id,
            metadata=copy.deepcopy(document.metadata),
            chapters=enriched_chapters,
            status=document.status,
            created_at=document.created_at,
            updated_at=self.clock(),
        )

        # 4. Enforce DocumentIntegrityValidator invariants
        self.validator.validate(enriched_document)

        logger.info(
            f"Completed Stage 1 semantic segmentation on Document {document.id}: "
            f"{enriched_document.total_blocks()} blocks classified and validated."
        )
        return enriched_document
