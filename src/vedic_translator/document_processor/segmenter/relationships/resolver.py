"""Rule-based deterministic relationship resolver for scripture verse and commentary units."""

import re
from uuid import UUID

from loguru import logger

from vedic_translator.core.models import (
    Block,
    BlockType,
    RelationshipConfidence,
    RoutingAction,
    Section,
    VerseUnit,
    VerseUnitType,
)
from vedic_translator.document_processor.segmenter.relationships.base import (
    IRelationshipResolver,
    RelationshipProfile,
)
from vedic_translator.document_processor.segmenter.relationships.profiles import (
    RAMCHARITA_MANAS_PROFILE,
)

DEV_METRICAL_PREFIXES = (
    "दो0ó",
    "चौ0ó",
    "सो0ó",
    "छं0ó",
    "श्लोक",
    "सोरठा",
    "छन्द",
    "दोहा",
    "चौपाई",
)
IAST_METRICAL_PREFIXES = ("Do.:", "Cau.:", "So.:", "Chh.:", "Sloka:", "Chaṁ.:")
IAST_DIACRITICS = set("āīūṛṝḷḹṅñṭḍṇśṣḥṁĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤṀ")


class RuleBasedRelationshipResolver(IRelationshipResolver):
    """Deterministic, profile-driven resolver mapping classified blocks into VerseUnits.

    Supports:
    - 1:1, 1:N, N:1, and N:M source-to-translation alignment.
    - Contiguity grouping for multi-line / split verses.
    - Footnote binding via bracketed or superscript anchors.
    - Non-destructive uncertainty handling with explicit evidence and reasoning.
    """

    def __init__(self, default_profile: RelationshipProfile | None = None) -> None:
        self.default_profile = default_profile or RAMCHARITA_MANAS_PROFILE

    def resolve_relationships(
        self,
        section: Section,
        profile: RelationshipProfile | None = None,
    ) -> list[VerseUnit]:
        """Resolve semantic relationships for blocks within a section.

        Returns an ordered list of VerseUnit objects referencing block UUIDs.
        Also updates block.verse_unit_ids with bidirectional pointers.
        """
        active_profile = profile or self.default_profile
        blocks = section.blocks

        if not blocks:
            return []

        # If section contains no verse blocks, standard literature requires no verse units
        has_verse_blocks = any(
            b.type in (BlockType.VERSE_DEVANAGARI, BlockType.VERSE_IAST)
            or self._is_devanagari_block(b, active_profile)
            for b in blocks
        )
        if not has_verse_blocks:
            return []

        verse_units: list[VerseUnit] = []
        pending_units: list[VerseUnit] = []  # Verses awaiting translation/commentary binding
        blocks_by_id: dict[UUID, Block] = {b.id: b for b in blocks}

        current_vu: VerseUnit | None = None
        last_verse_block: Block | None = None

        for block in blocks:
            b_text = block.source_text.strip()
            b_type = block.type

            # Check if an unspecialized or layout-classified block is verse, IAST, or translation
            is_unspecialized = b_type in (
                BlockType.PARAGRAPH,
                BlockType.BLOCKQUOTE,
                BlockType.QUOTE,
            )
            has_verse_indicator = bool(
                re.search(r"॥\s*\d+(?:\s*\([क-हA-Z]\))?\s*॥", b_text)
                or any(m in b_text for m in DEV_METRICAL_PREFIXES)
            )

            if is_unspecialized or (
                b_type in (BlockType.HEADING, BlockType.SUBHEADING) and has_verse_indicator
            ):
                if self._is_devanagari_block(block, active_profile):
                    b_type = BlockType.VERSE_DEVANAGARI
                    block.type = BlockType.VERSE_DEVANAGARI
                elif self._is_iast_block(block, active_profile):
                    b_type = BlockType.VERSE_IAST
                    block.type = BlockType.VERSE_IAST
                elif self._is_translation_block(
                    block,
                    has_pending_verse=bool(current_vu or pending_units),
                    profile=active_profile,
                ):
                    b_type = BlockType.TRANSLATION
                    block.type = BlockType.TRANSLATION

            # Check for metrical marker or verse anchor
            metrical_type, marker_token = self._detect_metrical_marker(b_text, active_profile)
            verse_num, num_token = self._detect_verse_number(b_text, active_profile)

            # -----------------------------------------------------------------
            # 1. Devanagari Verse Block Processing
            # -----------------------------------------------------------------
            if b_type == BlockType.VERSE_DEVANAGARI:
                # Determine if this starts a new verse or continues the previous one
                should_start_new = self._should_start_new_verse(
                    block=block,
                    current_vu=current_vu,
                    last_verse_block=last_verse_block,
                    has_marker=bool(metrical_type),
                    has_number=bool(verse_num),
                    profile=active_profile,
                )

                if should_start_new:
                    # If previous unit had no translation bound, it stays in pending_units for local pairing
                    if current_vu and current_vu not in pending_units:
                        pending_units.append(current_vu)

                    # Initialize a new VerseUnit
                    unit_type = metrical_type
                    if unit_type is None:
                        # Contextual fallback: if previous verse in section was CHAUPAI and this verse is numbered, it's CHAUPAI
                        if (
                            current_vu
                            and current_vu.unit_type == VerseUnitType.CHAUPAI
                            and verse_num
                        ):
                            unit_type = VerseUnitType.CHAUPAI
                        elif any(
                            kw in b_text for kw in ("नमः", "स्वाहा", "वषट्", "हुम्", "वौषट्", "फट्")
                        ):
                            unit_type = VerseUnitType.MANTRA
                        else:
                            unit_type = VerseUnitType.GENERIC_VERSE

                    canonical_id = self._build_canonical_id(
                        section, verse_num, unit_type, len(verse_units) + 1
                    )

                    evidence: list[str] = []
                    provenance_rules: list[str] = []
                    if marker_token:
                        evidence.append(f"Metrical marker '{marker_token}' detected")
                        provenance_rules.append("metrical_marker_prefix")
                    if num_token:
                        evidence.append(f"Verse anchor '{num_token}' detected")
                        provenance_rules.append("exact_numeric_anchor")

                    current_vu = VerseUnit(
                        unit_type=unit_type,
                        canonical_id=canonical_id,
                        original_script_block_ids=[block.id],
                        confidence=RelationshipConfidence(
                            overall_score=0.95 if (marker_token or num_token) else 0.75,
                            routing_action=(
                                RoutingAction.AUTO_ACCEPTED
                                if (marker_token or num_token)
                                else RoutingAction.AMBIGUOUS
                            ),
                            provenance_rules=provenance_rules or ["devanagari_block_start"],
                            evidence=evidence,
                            reasoning="New verse initiated by Devanagari verse block.",
                        ),
                        metadata={"section_index": section.section_index},
                    )
                    verse_units.append(current_vu)
                    pending_units.append(current_vu)
                    self._link_block_to_vu(block, current_vu)
                else:
                    # Contiguity grouping (split verse continuation)
                    if current_vu:
                        current_vu.original_script_block_ids.append(block.id)
                        current_vu.confidence.provenance_rules.append("contiguity_grouping")
                        current_vu.confidence.evidence.append(
                            f"Contiguous verse line Block {block.sequence_index}"
                        )
                        self._link_block_to_vu(block, current_vu)
                        # If continuation line contains the danda verse anchor (e.g. ॥ 188 ॥), update canonical ID
                        if verse_num and (
                            not current_vu.canonical_id
                            or not current_vu.canonical_id.endswith(verse_num)
                        ):
                            current_vu.canonical_id = self._build_canonical_id(
                                section, verse_num, current_vu.unit_type, len(verse_units)
                            )
                            if num_token:
                                current_vu.confidence.evidence.append(
                                    f"Verse anchor '{num_token}' detected"
                                )
                                if (
                                    "exact_numeric_anchor"
                                    not in current_vu.confidence.provenance_rules
                                ):
                                    current_vu.confidence.provenance_rules.append(
                                        "exact_numeric_anchor"
                                    )

                last_verse_block = block
                continue

            # -----------------------------------------------------------------
            # 2. Transliteration (IAST) Block Processing
            # -----------------------------------------------------------------
            if b_type == BlockType.VERSE_IAST:
                target_vu = current_vu or (pending_units[-1] if pending_units else None)
                if target_vu:
                    # Check spatial proximity (within local cluster of 4 blocks)
                    orig_blocks = [
                        blocks_by_id[bid]
                        for bid in target_vu.original_script_block_ids
                        if bid in blocks_by_id
                    ]
                    min_dist = (
                        min(abs(block.sequence_index - ob.sequence_index) for ob in orig_blocks)
                        if orig_blocks
                        else 999
                    )
                    if min_dist <= 4:
                        target_vu.transliteration_block_ids.append(block.id)
                        target_vu.confidence.provenance_rules.append("transliteration_pairing")
                        target_vu.confidence.evidence.append(
                            f"IAST transliteration Block {block.sequence_index}"
                        )
                        self._link_block_to_vu(block, target_vu)
                continue

            # -----------------------------------------------------------------
            # 3. Synonyms (Anvaya) Block Processing
            # -----------------------------------------------------------------
            if b_type == BlockType.SYNONYMS:
                target_vu = current_vu or (pending_units[-1] if pending_units else None)
                if target_vu:
                    target_vu.synonyms_block_ids.append(block.id)
                    target_vu.confidence.provenance_rules.append("synonyms_pairing")
                    target_vu.confidence.evidence.append(f"Synonyms Block {block.sequence_index}")
                    self._link_block_to_vu(block, target_vu)
                continue

            # -----------------------------------------------------------------
            # 4. Translation Block Processing (Flexible 1:1, 1:N, N:1)
            # -----------------------------------------------------------------
            if b_type == BlockType.TRANSLATION:
                is_composite, comp_range = self._detect_composite_translation(
                    b_text, active_profile
                )

                if is_composite and pending_units:
                    # N:1 shared translation binding with explicit composite anchor
                    # Only bind to pending units in local proximity (same page or adjacent, seq gap <= 15)
                    local_units: list[VerseUnit] = []
                    for p_vu in pending_units:
                        p_blocks = [
                            blocks_by_id[bid]
                            for bid in p_vu.original_script_block_ids
                            if bid in blocks_by_id
                        ]
                        if p_blocks:
                            p_page = p_blocks[-1].metadata.get("page")
                            cur_page = block.metadata.get("page")
                            if p_page is None or cur_page is None or abs(cur_page - p_page) <= 1:
                                local_units.append(p_vu)

                    if local_units:
                        for p_vu in local_units:
                            p_vu.translation_block_ids.append(block.id)
                            p_vu.confidence.provenance_rules.append("composite_translation_anchor")
                            p_vu.confidence.evidence.append(
                                f"Shared translation covering range '{comp_range}' at Block {block.sequence_index}"
                            )
                            p_vu.confidence.reasoning = f"Shared English translation block explicitly covering multiple verses ({comp_range})."
                            self._link_block_to_vu(block, p_vu)
                            if p_vu in pending_units:
                                pending_units.remove(p_vu)
                        current_vu = None
                elif pending_units:
                    # Single-verse translation binding:
                    # Only bind to the immediately preceding open verse unit (pending_units[-1])
                    p_vu = pending_units[-1]
                    p_blocks = [
                        blocks_by_id[bid]
                        for bid in p_vu.original_script_block_ids
                        if bid in blocks_by_id
                    ]
                    min_dist = (
                        min(abs(block.sequence_index - ob.sequence_index) for ob in p_blocks)
                        if p_blocks
                        else 999
                    )
                    p_page = p_blocks[-1].metadata.get("page") if p_blocks else None
                    cur_page = block.metadata.get("page")
                    is_local = (
                        p_page is None or cur_page is None or abs(cur_page - p_page) <= 1
                    ) and min_dist <= 6

                    if is_local:
                        if p_vu.translation_block_ids:
                            # 1:N continuation: only if immediately adjacent to last translation block
                            # and previous translation was not already terminated with a closing quote or number anchor
                            last_trans_blk = blocks_by_id.get(p_vu.translation_block_ids[-1])
                            last_text = last_trans_blk.source_text.strip() if last_trans_blk else ""
                            is_already_terminated = bool(
                                re.search(r'(?:\([0-9]+(?:\s*[A-Za-z])?\)|[”"\'’])\s*$', last_text)
                            )
                            is_procedural = bool(
                                re.search(
                                    r"\b(?:Karanyāsa|Aṅganyāsa|Dhyāna|Procedure|Nyāsa|Recitation|Pauses)\b",
                                    b_text,
                                    re.IGNORECASE,
                                )
                            )

                            if (
                                not is_already_terminated
                                and not is_procedural
                                and last_trans_blk
                                and block.sequence_index == last_trans_blk.sequence_index + 1
                                and cur_page == last_trans_blk.metadata.get("page")
                            ):
                                p_vu.translation_block_ids.append(block.id)
                                p_vu.confidence.provenance_rules.append("translation_continuation")
                                p_vu.confidence.evidence.append(
                                    f"Translation continuation Block {block.sequence_index}"
                                )
                                self._link_block_to_vu(block, p_vu)
                            else:
                                # Translation is complete or not adjacent -> close p_vu
                                pending_units.remove(p_vu)
                                current_vu = None
                        else:
                            p_vu.translation_block_ids.append(block.id)
                            p_vu.confidence.provenance_rules.append("translation_pairing")
                            p_vu.confidence.evidence.append(
                                f"Translation Block {block.sequence_index}"
                            )
                            self._link_block_to_vu(block, p_vu)
                    else:
                        # Distant translation without composite anchor -> do NOT attach!
                        logger.warning(
                            f"Translation block {block.sequence_index} on page {cur_page} rejected for distant verse {p_vu.canonical_id} (dist={min_dist})"
                        )
                        pending_units.remove(p_vu)
                        current_vu = None
                else:
                    logger.warning(
                        f"Unanchored TRANSLATION block {block.sequence_index} in section {section.id} with no active verse unit."
                    )
                continue

            # -----------------------------------------------------------------
            # 5. Commentary / Purport Processing
            # -----------------------------------------------------------------
            if b_type == BlockType.PURPORT:
                target_vu = current_vu or (verse_units[-1] if verse_units else None)
                if target_vu:
                    target_vu.commentary_block_ids.append(block.id)
                    target_vu.confidence.provenance_rules.append("commentary_pairing")
                    target_vu.confidence.evidence.append(
                        f"Purport/Commentary Block {block.sequence_index}"
                    )
                    self._link_block_to_vu(block, target_vu)
                continue

            # -----------------------------------------------------------------
            # 6. Footnote Block Processing
            # -----------------------------------------------------------------
            if b_type == BlockType.FOOTNOTE:
                target_vu = self._find_referencing_verse_unit(
                    block, verse_units, blocks_by_id, active_profile
                )
                if target_vu:
                    target_vu.footnote_block_ids.append(block.id)
                    target_vu.confidence.provenance_rules.append("footnote_binding")
                    target_vu.confidence.evidence.append(
                        f"Bound footnote Block {block.sequence_index}"
                    )
                    self._link_block_to_vu(block, target_vu)
                continue

        # ---------------------------------------------------------------------
        # Final Pass: Score Calibration & Incompleteness Invariants
        # ---------------------------------------------------------------------
        for vu in verse_units:
            self._finalize_verse_unit(vu, blocks_by_id, active_profile)

        return verse_units

    # =========================================================================
    # Helper & Diagnostic Methods
    # =========================================================================

    def _is_devanagari_block(self, block: Block, profile: RelationshipProfile) -> bool:
        """Check if block is primarily Devanagari script or contains genuine Devanagari metrical markers."""
        text = block.source_text.strip()
        if not text:
            return False

        detected_role = block.metadata.get("detected_script_role")

        devanagari_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
        alpha_count = sum(1 for ch in text if ch.isalpha())
        latin_count = sum(1 for ch in text if ("a" <= ch <= "z" or "A" <= ch <= "Z"))

        # Strict script guard: Predominantly Latin text must NEVER be accepted as original Devanagari
        if latin_count > 0 and (latin_count / max(1, alpha_count)) > 0.60:
            return False

        if detected_role == "DEVANAGARI":
            if devanagari_count > 0 or any(m in text for m in DEV_METRICAL_PREFIXES):
                return True

        for marker in DEV_METRICAL_PREFIXES:
            if marker in text:
                return True

        if alpha_count > 0 and (devanagari_count / alpha_count) >= 0.35:
            return True

        return False

    def _is_iast_block(self, block: Block, profile: RelationshipProfile) -> bool:
        """Check if block text contains IAST transliteration or Roman verse markers."""
        text = block.source_text.strip()
        if not text:
            return False

        detected_role = block.metadata.get("detected_script_role")
        if detected_role == "PROSE":
            # If PDF extractor already verified this is English prose (Nalandatim),
            # it can ONLY be IAST if it starts with an explicit metrical marker
            for marker in IAST_METRICAL_PREFIXES:
                if text.startswith(marker) or f" {marker}" in text[:30]:
                    return True
            return False

        if detected_role == "TRANSLITERATION":
            return True

        for marker in IAST_METRICAL_PREFIXES:
            if text.startswith(marker) or f" {marker}" in text[:30]:
                return True

        words = text.split()
        if not words:
            return False

        count = sum(1 for ch in text if ch in IAST_DIACRITICS)
        devanagari_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
        if devanagari_count > 0:
            return False

        # For text without PDF metadata: transliteration verses have high density of diacritics
        # while English prose mentioning proper names has very low density
        if count >= 2 and len(words) <= 25:
            return True
        if count >= 6 and (count / len(words)) >= 0.25:
            return True

        return False

    def _is_translation_block(
        self, block: Block, has_pending_verse: bool, profile: RelationshipProfile
    ) -> bool:
        """Check if block text is an English translation block."""
        text = block.source_text.strip()
        if not text:
            return False

        if self._is_devanagari_block(block, profile) or self._is_iast_block(block, profile):
            return False

        # 1. Composite translation anchor (e.g. (1-4) or Chaupais 1-4)
        if self._detect_composite_translation(text, profile)[0]:
            return True

        # 2. Specific translation anchors
        for pat in profile.translation_anchor_patterns:
            if re.search(pat, text):
                if pat.startswith('^["“]'):
                    return has_pending_verse
                return True

        # 3. If verse is pending and this block is predominantly Latin/English (not Devanagari)
        if has_pending_verse:
            latin_count = sum(1 for ch in text if ("a" <= ch <= "z" or "A" <= ch <= "Z"))
            alpha_count = sum(1 for ch in text if ch.isalpha())
            if alpha_count > 0 and (latin_count / alpha_count) >= 0.60:
                return True

        return False

    def _detect_metrical_marker(
        self, text: str, profile: RelationshipProfile
    ) -> tuple[VerseUnitType | None, str | None]:
        """Detect metrical marker prefix in block text."""
        for marker, v_type_str in profile.metrical_marker_patterns.items():
            if text.startswith(marker) or f" {marker}" in text[:30]:
                try:
                    return VerseUnitType(v_type_str), marker
                except ValueError:
                    return VerseUnitType.GENERIC_VERSE, marker
        return None, None

    def _detect_verse_number(
        self, text: str, profile: RelationshipProfile
    ) -> tuple[str | None, str | None]:
        """Detect verse number anchor in block text."""
        for pattern in profile.verse_number_patterns:
            match = re.search(pattern, text)
            if match:
                num = match.group(1) if match.groups() else match.group(0)
                return num.strip(), match.group(0)
        return None, None

    def _detect_composite_translation(
        self, text: str, profile: RelationshipProfile
    ) -> tuple[bool, str | None]:
        """Detect whether a translation block explicitly spans multiple verses (N:1)."""
        for pattern in profile.composite_translation_patterns:
            match = re.search(pattern, text[:60])
            if match:
                if len(match.groups()) >= 2:
                    return True, f"{match.group(1)}-{match.group(2)}"
                return True, match.group(0)
        return False, None

    def _should_start_new_verse(
        self,
        block: Block,
        current_vu: VerseUnit | None,
        last_verse_block: Block | None,
        has_marker: bool,
        has_number: bool,
        profile: RelationshipProfile,
    ) -> bool:
        """Determine if a Devanagari block starts a new VerseUnit."""
        if current_vu is None:
            return True

        # Explicit metrical marker always starts a new verse
        if has_marker:
            return True

        # If previous verse unit already has a translation or transliteration bound,
        # subsequent Devanagari block MUST start a new verse
        if current_vu.translation_block_ids or current_vu.transliteration_block_ids:
            return True

        # If previous Devanagari ended with an explicit danda verse number (e.g., ॥ 188 ॥ or ॥ 1 ॥)
        if last_verse_block:
            last_text = last_verse_block.source_text.strip()
            if re.search(r"॥\s*\d+(?:\s*\([क-हA-Z]\))?\s*॥\s*$", last_text):
                return True
            if re.search(r"\|\s*\d+(?:\s*\([क-हA-Z]\))?\s*\|\s*$", last_text):
                return True

        # If contiguity grouping is disabled
        if not profile.enable_contiguity_grouping:
            return True

        return False

    def _build_canonical_id(
        self,
        section: Section,
        verse_num: str | None,
        unit_type: VerseUnitType,
        sequence_num: int,
    ) -> str:
        """Construct a deterministic canonical identifier for the verse unit."""
        sec_idx = section.section_index
        prefix = {
            VerseUnitType.CHAUPAI: "Cau.",
            VerseUnitType.DOHA: "Do.",
            VerseUnitType.SORATHA: "So.",
            VerseUnitType.CHHANDA: "Chh.",
            VerseUnitType.SLOKA: "Sl.",
            VerseUnitType.MANTRA: "M.",
        }.get(unit_type, "V.")

        if verse_num:
            return f"{sec_idx}.{verse_num}"
        return f"{prefix} {sec_idx}.{sequence_num}"

    def _link_block_to_vu(self, block: Block, vu: VerseUnit) -> None:
        """Establish bidirectional relationship pointer from block to verse unit."""
        if vu.id not in block.verse_unit_ids:
            block.verse_unit_ids.append(vu.id)

    def _find_referencing_verse_unit(
        self,
        footnote_block: Block,
        verse_units: list[VerseUnit],
        blocks_by_id: dict[UUID, Block],
        profile: RelationshipProfile,
    ) -> VerseUnit | None:
        """Find the VerseUnit that contains an in-text anchor pointing to this footnote."""
        if not verse_units:
            return None

        fn_text = footnote_block.source_text.strip()
        match = re.match(r"^(?:\[\^?(\d+)\]|(\d+)\.|\((\d+)\))", fn_text)
        if match:
            anchor_num = next(g for g in match.groups() if g is not None)
            anchor_patterns = [f"[{anchor_num}]", f"({anchor_num})", f"[^{anchor_num}]"]
            for vu in reversed(verse_units):
                vu_block_ids = (
                    vu.translation_block_ids
                    + vu.commentary_block_ids
                    + vu.original_script_block_ids
                )
                for b_id in vu_block_ids:
                    b = blocks_by_id.get(b_id)
                    if b and any(pat in b.source_text for pat in anchor_patterns):
                        return vu

        return verse_units[-1] if verse_units else None

    def _finalize_verse_unit(
        self,
        vu: VerseUnit,
        blocks_by_id: dict[UUID, Block],
        profile: RelationshipProfile,
    ) -> None:
        """Compute final confidence scores, incompleteness tags, and routing decisions."""
        missing: list[str] = []
        if not vu.original_script_block_ids:
            missing.append("original_script")
        if not vu.translation_block_ids:
            missing.append("translation")

        vu.missing_components = missing
        vu.is_complete = len(missing) == 0

        # Anchor score
        has_anchor = any(
            r in vu.confidence.provenance_rules
            for r in (
                "metrical_marker_prefix",
                "exact_numeric_anchor",
                "composite_translation_anchor",
            )
        )
        anchor_score = 1.0 if has_anchor else 0.60

        # Sequence score
        seq_score = 1.0 if vu.is_complete else 0.50

        # Dynamic Spatial proximity score:
        spatial_score = 1.0
        if vu.original_script_block_ids and vu.translation_block_ids:
            orig_blocks = [
                blocks_by_id[bid] for bid in vu.original_script_block_ids if bid in blocks_by_id
            ]
            trans_blocks = [
                blocks_by_id[bid] for bid in vu.translation_block_ids if bid in blocks_by_id
            ]
            if orig_blocks and trans_blocks:
                last_orig = orig_blocks[-1]
                first_trans = trans_blocks[0]
                seq_gap = abs(first_trans.sequence_index - last_orig.sequence_index)
                page_orig = last_orig.metadata.get("page", 0)
                page_trans = first_trans.metadata.get("page", 0)
                page_gap = abs(page_trans - page_orig)

                if page_gap > 1:
                    spatial_score = 0.0
                elif page_gap == 1:
                    spatial_score = 0.70
                elif seq_gap <= 2:
                    spatial_score = 1.0
                elif seq_gap <= 4:
                    spatial_score = 0.85
                else:
                    spatial_score = max(0.40, 1.0 - 0.10 * (seq_gap - 2))
        elif not vu.translation_block_ids:
            spatial_score = 0.50

        # Script consistency score: check that every original block is genuine Devanagari
        script_score = 1.0
        for bid in vu.original_script_block_ids:
            b = blocks_by_id.get(bid)
            if b:
                text = b.source_text.strip()
                latin_count = sum(1 for ch in text if ("a" <= ch <= "z" or "A" <= ch <= "Z"))
                alpha_count = sum(1 for ch in text if ch.isalpha())
                if alpha_count > 0 and (latin_count / alpha_count) > 0.60:
                    script_score = 0.0

        overall = (
            profile.weight_anchor_match * anchor_score
            + profile.weight_sequence_flow * seq_score
            + profile.weight_spatial_proximity * spatial_score
            + profile.weight_script_consistency * script_score
        )
        overall = max(0.0, min(1.0, round(overall, 4)))

        vu.confidence.overall_score = overall
        vu.confidence.component_scores = {
            "anchor_match": anchor_score,
            "sequence_flow": seq_score,
            "spatial_proximity": round(spatial_score, 4),
            "script_consistency": script_score,
        }

        # Apply configurable threshold gates:
        # Strict invariant: AUTO_ACCEPTED requires completeness AND clean script
        if overall >= profile.threshold_auto_accept and vu.is_complete and script_score >= 0.8:
            vu.confidence.routing_action = RoutingAction.AUTO_ACCEPTED
            if not vu.confidence.reasoning:
                vu.confidence.reasoning = "Unambiguous structural and sequential alignment."
        elif overall >= profile.threshold_ambiguous:
            vu.confidence.routing_action = RoutingAction.AMBIGUOUS
            if not vu.confidence.reasoning:
                vu.confidence.reasoning = f"Structural ambiguity detected (missing: {', '.join(missing) if missing else 'none'})."
        else:
            vu.confidence.routing_action = RoutingAction.FLAGGED_FOR_REVIEW
            if not vu.confidence.reasoning:
                vu.confidence.reasoning = (
                    "Low structural confidence; unforced relationship requiring human review."
                )
