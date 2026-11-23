"""DocumentIntegrityValidator for structural, relational, and sequence invariants."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from vedic_translator.core.exceptions import ReferentialIntegrityError
from vedic_translator.core.models import Document


class IntegrityReport(BaseModel):
    """Diagnostic report from document integrity validation."""

    is_valid: bool
    total_blocks_checked: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentIntegrityValidator:
    """Validator enforcing closed-universe relational, hierarchical, and sequence integrity."""

    def __init__(self, raise_on_error: bool = True) -> None:
        self.raise_on_error = raise_on_error

    def validate(self, document: Document) -> IntegrityReport:
        """Validate all structural, sequence, and relational invariants on an AST."""
        errors: list[str] = []
        warnings: list[str] = []
        all_block_ids: set[UUID] = set()
        block_by_id: dict[UUID, Any] = {}
        total_blocks = 0
        last_seq_index = -1

        # 1. Structural Hierarchy Invariants
        if not document.chapters:
            warnings.append(f"Document {document.id} contains no chapters.")

        for ch_idx, chapter in enumerate(document.chapters):
            if not chapter.sections:
                warnings.append(
                    f"Chapter {chapter.id} (index {chapter.chapter_index}) contains no sections."
                )

            for sec_idx, section in enumerate(chapter.sections):
                for b_idx, block in enumerate(section.blocks):
                    total_blocks += 1

                    # Check 1: Block ID uniqueness
                    if block.id in all_block_ids:
                        errors.append(
                            f"Duplicate Block ID detected: {block.id} at chapter {ch_idx}, section {sec_idx}, block {b_idx}."
                        )
                    all_block_ids.add(block.id)
                    block_by_id[block.id] = block

                    # Check 2: Sequence index monotonicity
                    if block.sequence_index <= last_seq_index and total_blocks > 1:
                        errors.append(
                            f"Discontinuous sequence_index at Block {block.id}: expected > {last_seq_index}, got {block.sequence_index}."
                        )
                    last_seq_index = block.sequence_index

                    # Check 3: Bounded confidence score
                    if block.provenance:
                        conf = block.provenance.confidence
                        if not (0.0 <= conf <= 1.0):
                            errors.append(
                                f"Unbounded confidence score at Block {block.id}: {conf} not in [0.0, 1.0]."
                            )

                    # Check 4: Block relationship references (no internal duplicates)
                    if block.verse_unit_ids:
                        if len(block.verse_unit_ids) != len(set(block.verse_unit_ids)):
                            errors.append(
                                f"Duplicate verse_unit_ids in Block {block.id}: {block.verse_unit_ids}"
                            )

        # 2. Section-level relationship checks (if verse_units exist)
        for chapter in document.chapters:
            for section in chapter.sections:
                verse_units = getattr(section, "verse_units", [])
                section_block_ids = {b.id for b in section.blocks}
                section_vu_ids = {vu.id for vu in verse_units}

                for vu in verse_units:
                    all_vu_blocks: list[UUID] = []
                    for attr in [
                        "original_script_block_ids",
                        "transliteration_block_ids",
                        "synonyms_block_ids",
                        "translation_block_ids",
                        "commentary_block_ids",
                        "footnote_block_ids",
                    ]:
                        block_ids = getattr(vu, attr, [])
                        # Invariant: No duplicate IDs within a component list
                        if len(block_ids) != len(set(block_ids)):
                            errors.append(
                                f"VerseUnit {vu.id} has duplicate block IDs in {attr}: {block_ids}"
                            )
                        all_vu_blocks.extend(block_ids)

                        # Invariant: Every referenced block ID must exist within the document
                        for b_id in block_ids:
                            if b_id not in all_block_ids:
                                errors.append(
                                    f"VerseUnit {vu.id} references non-existent Block ID {b_id} in {attr}."
                                )
                            elif b_id not in section_block_ids:
                                errors.append(
                                    f"VerseUnit {vu.id} in Section {section.id} references Block ID {b_id} "
                                    f"belonging to a different section (section boundary bleeding)."
                                )

                    # Invariant: Bidirectional link check
                    for b_id in all_vu_blocks:
                        if b_id in block_by_id:
                            target_block = block_by_id[b_id]
                            if vu.id not in target_block.verse_unit_ids:
                                errors.append(
                                    f"Missing bidirectional link: Block {b_id} does not contain VerseUnit ID {vu.id} in verse_unit_ids."
                                )

                    # Invariant: Confidence bounds
                    vu_conf = getattr(vu, "confidence", None)
                    if vu_conf:
                        if not (0.0 <= vu_conf.overall_score <= 1.0):
                            errors.append(
                                f"Unbounded confidence score at VerseUnit {vu.id}: {vu_conf.overall_score} not in [0.0, 1.0]."
                            )
                        for c_name, c_score in vu_conf.component_scores.items():
                            if not (0.0 <= c_score <= 1.0):
                                errors.append(
                                    f"Unbounded component score '{c_name}' at VerseUnit {vu.id}: {c_score} not in [0.0, 1.0]."
                                )

                # Invariant: Blocks in section must only reference VerseUnits belonging to that section
                for block in section.blocks:
                    for vu_id in block.verse_unit_ids:
                        if vu_id not in section_vu_ids:
                            errors.append(
                                f"Block {block.id} references non-existent or foreign VerseUnit ID {vu_id} in Section {section.id}."
                            )

        is_valid = len(errors) == 0
        report = IntegrityReport(
            is_valid=is_valid,
            total_blocks_checked=total_blocks,
            errors=errors,
            warnings=warnings,
        )

        if not is_valid and self.raise_on_error:
            raise ReferentialIntegrityError(
                f"Document integrity validation failed with {len(errors)} error(s).",
                details={"errors": errors[:10]},
            )

        return report
