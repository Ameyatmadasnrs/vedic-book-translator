"""Unit tests for Stage 2 Relationship Resolution and VerseUnit models."""

from uuid import uuid4

import pytest

from vedic_translator.core.exceptions import ReferentialIntegrityError
from vedic_translator.core.models import (
    Block,
    BlockType,
    Chapter,
    Document,
    DocumentMetadata,
    RelationshipConfidence,
    RoutingAction,
    Section,
    VerseUnit,
    VerseUnitType,
)
from vedic_translator.document_processor.segmenter.pipeline import SegmenterPipeline
from vedic_translator.document_processor.segmenter.relationships.profiles import (
    RAMCHARITA_MANAS_PROFILE,
    create_standard_prose_profile,
)
from vedic_translator.document_processor.segmenter.relationships.resolver import (
    RuleBasedRelationshipResolver,
)
from vedic_translator.document_processor.segmenter.validator import (
    DocumentIntegrityValidator,
)


def make_block(
    b_type: BlockType,
    text: str,
    seq: int = 0,
    verse_num: str | None = None,
) -> Block:
    """Helper to construct a simple Block with sequential defaults."""
    return Block(
        id=uuid4(),
        type=b_type,
        source_text=text,
        sequence_index=seq,
        verse_number=verse_num,
    )


def test_standard_prose_section_has_no_verse_units() -> None:
    """Test that a pure prose section produces no verse units."""
    blocks = [
        make_block(BlockType.HEADING, "Chapter 1: The Beginning", seq=1),
        make_block(BlockType.PARAGRAPH, "This is an introductory narrative paragraph.", seq=2),
        make_block(BlockType.PARAGRAPH, "This is a second narrative paragraph.", seq=3),
    ]
    section = Section(section_index=1, blocks=blocks)
    resolver = RuleBasedRelationshipResolver(default_profile=create_standard_prose_profile())

    verse_units = resolver.resolve_relationships(section)
    assert verse_units == []
    for b in blocks:
        assert b.verse_unit_ids == []


def test_single_chaupai_1_to_1_translation() -> None:
    """Test standard 1:1 mapping between an Awadhi Chaupai and its English translation."""
    v_block = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó बंदउँ गुरु पद पदुम परागा । सुरुचि सुबास सरस अनुरागा ॥ 1 ॥",
        seq=1,
    )
    t_block = make_block(
        BlockType.TRANSLATION,
        "(1) I bow to the lotus feet of my Guru, full of sweetness and fragrant devotion.",
        seq=2,
    )
    section = Section(section_index=1, blocks=[v_block, t_block])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 1
    vu = verse_units[0]
    assert vu.unit_type == VerseUnitType.CHAUPAI
    assert vu.canonical_id == "1.1"
    assert vu.original_script_block_ids == [v_block.id]
    assert vu.translation_block_ids == [t_block.id]
    assert vu.is_complete is True
    assert vu.missing_components == []
    assert vu.confidence.routing_action == RoutingAction.AUTO_ACCEPTED
    assert vu.confidence.overall_score >= 0.85
    assert "metrical_marker_prefix" in vu.confidence.provenance_rules
    assert any("चौ0ó" in ev for ev in vu.confidence.evidence)

    # Check bidirectional link
    assert vu.id in v_block.verse_unit_ids
    assert vu.id in t_block.verse_unit_ids


def test_split_verse_contiguity_grouping() -> None:
    """Test grouping of contiguous split Devanagari lines into a single VerseUnit."""
    line1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो0ó श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि ।",
        seq=1,
    )
    line2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि ॥ 188 ॥",
        seq=2,
    )
    t_block = make_block(
        BlockType.TRANSLATION,
        "(188) Having cleansed the mirror of my mind with the dust of the holy guru's feet...",
        seq=3,
    )
    section = Section(section_index=1, blocks=[line1, line2, t_block])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 1
    vu = verse_units[0]
    assert vu.unit_type == VerseUnitType.DOHA
    assert vu.original_script_block_ids == [line1.id, line2.id]
    assert vu.translation_block_ids == [t_block.id]
    assert "contiguity_grouping" in vu.confidence.provenance_rules
    assert vu.is_complete is True

    # Bidirectional links
    assert vu.id in line1.verse_unit_ids
    assert vu.id in line2.verse_unit_ids
    assert vu.id in t_block.verse_unit_ids


def test_one_verse_to_multiple_translations_1_to_n() -> None:
    """Test 1:N mapping where a single verse has its translation split across two paragraphs."""
    v_block = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó जेहि सुमिरत सिधि होइ गन नायक करिबर बदन ॥ 1 ॥",
        seq=1,
    )
    t_block1 = make_block(
        BlockType.TRANSLATION,
        "Remembering whom all accomplishments are attained, the lord of Ganas...",
        seq=2,
    )
    t_block2 = make_block(
        BlockType.TRANSLATION,
        "May that very Ganesha, the elephant-faced deity, bestow His boundless grace upon us.",
        seq=3,
    )
    section = Section(section_index=1, blocks=[v_block, t_block1, t_block2])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 1
    vu = verse_units[0]
    assert vu.original_script_block_ids == [v_block.id]
    assert vu.translation_block_ids == [t_block1.id, t_block2.id]
    assert vu.is_complete is True
    assert vu.id in t_block1.verse_unit_ids
    assert vu.id in t_block2.verse_unit_ids


def test_composite_shared_translation_n_to_1() -> None:
    """Test N:1 mapping where multiple verses share a single joint translation block."""
    chaupai1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó प्रथम बंदि गुरु पद पदुम परागा ॥ 1 ॥",
        seq=1,
    )
    chaupai2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó बहुरि बंदि खल गन सतिभाएँ ॥ 2 ॥",
        seq=2,
    )
    shared_trans = make_block(
        BlockType.TRANSLATION,
        "(1-2) First I adore the lotus feet of the preceptor; next I greet the wicked with genuine feeling.",
        seq=3,
    )
    section = Section(section_index=1, blocks=[chaupai1, chaupai2, shared_trans])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 2
    vu1, vu2 = verse_units[0], verse_units[1]

    assert vu1.original_script_block_ids == [chaupai1.id]
    assert vu1.translation_block_ids == [shared_trans.id]
    assert vu2.original_script_block_ids == [chaupai2.id]
    assert vu2.translation_block_ids == [shared_trans.id]

    # Shared translation block references both verse units
    assert vu1.id in shared_trans.verse_unit_ids
    assert vu2.id in shared_trans.verse_unit_ids
    assert len(shared_trans.verse_unit_ids) == 2


def test_full_scripture_apparatus_mapping() -> None:
    """Test mapping an apparatus with Devanagari, IAST, Synonyms, Translation, Purport, and Footnote."""
    v_dev = make_block(
        BlockType.VERSE_DEVANAGARI,
        "देहिनोऽस्मिन्यथा देहे कौमारं यौवनं जरा ॥ 13 ॥",
        seq=1,
    )
    v_iast = make_block(
        BlockType.VERSE_IAST,
        "dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā",
        seq=2,
    )
    syn = make_block(
        BlockType.SYNONYMS,
        "dehinaḥ — of the embodied; asmin — in this; dehe — in the body; kaumāram — boyhood;",
        seq=3,
    )
    trans = make_block(
        BlockType.TRANSLATION,
        "As the embodied soul continuously passes, in this body, from boyhood to youth to old age...",
        seq=4,
    )
    purport = make_block(
        BlockType.PURPORT,
        "Since every living entity is an individual soul, each is changing his body at every moment.",
        seq=5,
    )
    fn = make_block(
        BlockType.FOOTNOTE,
        "[1] Cf. Katha Upanishad 1.2.18 on the eternity of the conscious self.",
        seq=6,
    )

    section = Section(
        section_index=1,
        blocks=[v_dev, v_iast, syn, trans, purport, fn],
    )
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 1
    vu = verse_units[0]
    assert vu.original_script_block_ids == [v_dev.id]
    assert vu.transliteration_block_ids == [v_iast.id]
    assert vu.synonyms_block_ids == [syn.id]
    assert vu.translation_block_ids == [trans.id]
    assert vu.commentary_block_ids == [purport.id]
    assert vu.footnote_block_ids == [fn.id]
    assert vu.is_complete is True
    assert vu.confidence.routing_action == RoutingAction.AUTO_ACCEPTED


def test_missing_translation_marked_ambiguous() -> None:
    """Test that a verse with missing translation is tagged incomplete and marked AMBIGUOUS."""
    v_dev = make_block(
        BlockType.VERSE_DEVANAGARI,
        "सोरठाó जेहि सुमिरत सिधि होइ ॥",
        seq=1,
    )
    section = Section(section_index=1, blocks=[v_dev])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)

    verse_units = resolver.resolve_relationships(section)

    assert len(verse_units) == 1
    vu = verse_units[0]
    assert vu.is_complete is False
    assert "translation" in vu.missing_components
    assert vu.confidence.routing_action in (
        RoutingAction.AMBIGUOUS,
        RoutingAction.FLAGGED_FOR_REVIEW,
    )
    assert vu.confidence.reasoning is not None


def test_pipeline_integration_and_validator_passes() -> None:
    """Test full integration through SegmenterPipeline, verifying DocumentIntegrityValidator passes."""
    line1 = make_block(BlockType.VERSE_DEVANAGARI, "चौ0ó प्रथम बंदि गुरु पद पदुम परागा ॥ 1 ॥", seq=1)
    line2 = make_block(
        BlockType.TRANSLATION, "(1) First I adore the lotus feet of the guru.", seq=2
    )

    doc = Document(
        metadata=DocumentMetadata(title="Ramcharit Manas Test"),
        chapters=[
            Chapter(
                chapter_index=1,
                title="Bala Kanda",
                sections=[Section(section_index=1, blocks=[line1, line2])],
            )
        ],
    )

    pipeline = SegmenterPipeline(enable_relationship_resolution=True)
    enriched_doc = pipeline.segment(doc)

    assert enriched_doc.total_blocks() == 2
    sec = enriched_doc.chapters[0].sections[0]
    assert len(sec.verse_units) == 1
    vu = sec.verse_units[0]
    assert vu.unit_type == VerseUnitType.CHAUPAI

    # Validator must pass without raising
    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(enriched_doc)
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_validator_catches_non_existent_block_id_in_verse_unit() -> None:
    """Test that DocumentIntegrityValidator raises error if a VerseUnit references a non-existent block."""
    b = make_block(BlockType.PARAGRAPH, "Hello", seq=1)
    fake_id = uuid4()
    vu = VerseUnit(
        original_script_block_ids=[fake_id],
        confidence=RelationshipConfidence(
            overall_score=0.9,
            routing_action=RoutingAction.AUTO_ACCEPTED,
        ),
    )
    section = Section(section_index=1, blocks=[b], verse_units=[vu])
    doc = Document(
        metadata=DocumentMetadata(title="Test"),
        chapters=[Chapter(chapter_index=1, title="Ch1", sections=[section])],
    )

    validator = DocumentIntegrityValidator(raise_on_error=True)
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(doc)
    assert "references non-existent Block ID" in str(exc_info.value)


def test_validator_catches_missing_bidirectional_link() -> None:
    """Test that DocumentIntegrityValidator raises error if block does not link back to VerseUnit."""
    b = make_block(BlockType.VERSE_DEVANAGARI, "Verse text", seq=1)
    vu = VerseUnit(
        original_script_block_ids=[b.id],
        confidence=RelationshipConfidence(
            overall_score=0.9,
            routing_action=RoutingAction.AUTO_ACCEPTED,
        ),
    )
    # Intentionally do not add vu.id to b.verse_unit_ids
    section = Section(section_index=1, blocks=[b], verse_units=[vu])
    doc = Document(
        metadata=DocumentMetadata(title="Test"),
        chapters=[Chapter(chapter_index=1, title="Ch1", sections=[section])],
    )

    validator = DocumentIntegrityValidator(raise_on_error=True)
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(doc)
    assert "Missing bidirectional link" in str(exc_info.value)


def test_validator_catches_section_boundary_bleeding() -> None:
    """Test that DocumentIntegrityValidator catches a VerseUnit referencing a block in another section."""
    b1 = make_block(BlockType.VERSE_DEVANAGARI, "Section 1 Verse", seq=1)
    b2 = make_block(BlockType.TRANSLATION, "Section 2 Translation", seq=2)

    vu1 = VerseUnit(
        original_script_block_ids=[b1.id],
        translation_block_ids=[b2.id],  # b2 is in section 2!
        confidence=RelationshipConfidence(
            overall_score=0.9,
            routing_action=RoutingAction.AUTO_ACCEPTED,
        ),
    )
    b1.verse_unit_ids = [vu1.id]
    b2.verse_unit_ids = [vu1.id]

    sec1 = Section(section_index=1, blocks=[b1], verse_units=[vu1])
    sec2 = Section(section_index=2, blocks=[b2], verse_units=[])
    doc = Document(
        metadata=DocumentMetadata(title="Test"),
        chapters=[Chapter(chapter_index=1, title="Ch1", sections=[sec1, sec2])],
    )

    validator = DocumentIntegrityValidator(raise_on_error=True)
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(doc)
    assert "section boundary bleeding" in str(exc_info.value)


# =============================================================================
# Acceptance Audit Regression Tests for the 5 Critical Defects
# =============================================================================


def test_defect_1_distant_translation_rejected_sati_episode() -> None:
    """Defect 1: Distant English translation blocks across pages must NOT attach to pending verses."""
    v1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó मैं संकर कर कहा न माना। निज अग्यानु राम पर आना॥ 1॥",
        seq=1,
    )
    v1.metadata["page"] = 85
    v2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "जाइ कहब मैं कहा बुझाई। बिकल बिलोचन वारि बहाई॥ 2॥",
        seq=2,
    )
    v2.metadata["page"] = 85

    # Distant English translation block on page 87 (distance = 10, page gap = 2)
    distant_trans = make_block(
        BlockType.TRANSLATION,
        "Taking milk and water together, a swan drinks only the milk and leaves the water.",
        seq=12,
    )
    distant_trans.metadata["page"] = 87

    section = Section(section_index=1, blocks=[v1, v2, distant_trans])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 2
    # Neither verse should have swallowed the distant translation
    for u in units:
        assert distant_trans.id not in u.translation_block_ids
        assert u.translation_block_ids == []
        assert u.is_complete is False
        assert "translation" in u.missing_components
        assert u.confidence.routing_action in (
            RoutingAction.AMBIGUOUS,
            RoutingAction.FLAGGED_FOR_REVIEW,
        )


def test_defect_2_devanagari_blockquote_merged_via_contiguity() -> None:
    """Defect 2: Devanagari verse blocks classified as BLOCKQUOTE must NOT be ignored and must merge via contiguity."""
    line1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो0ó कौसल्यादि नारि प्रिय सब आचरन पुनीत।",
        seq=1,
    )
    # Simulating ContentClassifier tagging an indented second line as BLOCKQUOTE
    line2 = make_block(
        BlockType.BLOCKQUOTE,
        "पति अनुकूल प्रेम दृढ़ हरि पद कमल बिनीत॥ 188॥",
        seq=2,
    )
    trans = make_block(
        BlockType.TRANSLATION,
        "(188) Kausalyā and his other beloved consorts were all of holy demeanour...",
        seq=3,
    )

    section = Section(section_index=1, blocks=[line1, line2, trans])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 1
    doha = units[0]
    assert doha.unit_type == VerseUnitType.DOHA
    assert doha.canonical_id == "1.188"
    assert doha.original_script_block_ids == [line1.id, line2.id]
    assert doha.translation_block_ids == [trans.id]
    assert line2.type == BlockType.VERSE_DEVANAGARI
    assert "contiguity_grouping" in doha.confidence.provenance_rules
    assert "exact_numeric_anchor" in doha.confidence.provenance_rules
    assert doha.confidence.routing_action == RoutingAction.AUTO_ACCEPTED


def test_defect_3_line_level_split_of_mixed_iast_and_english() -> None:
    """Defect 3: Lines of transliteration (Nalandahel) and English (Nalandatim) are cleanly distinguished."""
    from vedic_translator.document_processor.extractors.pdf import PDFExtractor

    extractor = PDFExtractor()
    # Line 1: Nalandahel (transliteration)
    spans_iast = [
        {
            "font": "NalandahelBold",
            "text": "Do.: kausalyādi nāri priya saba ācarana punīta,",
            "raw_text": "Do.: kausalyådi...",
        }
    ]
    role1 = extractor._classify_line_role(
        spans_iast, "Do.: kausalyādi nāri priya saba ācarana punīta,"
    )
    assert role1 == "TRANSLITERATION"

    # Line 2: Nalandatim (English translation)
    spans_eng = [
        {
            "font": "Nalandatim",
            "text": "Kausalyā and his other beloved consorts were all of holy demeanour...",
            "raw_text": "Kausalyå...",
        }
    ]
    role2 = extractor._classify_line_role(
        spans_eng, "Kausalyā and his other beloved consorts were all of holy demeanour..."
    )
    assert role2 == "PROSE"

    # Line 3: Chanakya (Devanagari verse)
    spans_dev = [
        {"font": "ChanakyaBold", "text": "चौ0ó एक बार भूपति मन माहीं...", "raw_text": "øı0ó..."}
    ]
    role3 = extractor._classify_line_role(spans_dev, "चौ0ó एक बार भूपति मन माहीं...")
    assert role3 == "DEVANAGARI"


def test_defect_4_english_paragraph_ending_in_number_rejected_as_original() -> None:
    """Defect 4: English paragraphs ending with (2) or (188) must NEVER be accepted as original script."""
    eng_block = make_block(
        BlockType.PARAGRAPH,
        "He told the Guru all his joys and sorrows; the sage Vasiṣṭha comforted him in many ways and said: "
        "Take heart and wait; you will have four sons who will relieve the agony of devotees. (2)",
        seq=1,
    )
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    # The resolver must reject this block as Devanagari original script
    assert resolver._is_devanagari_block(eng_block, RAMCHARITA_MANAS_PROFILE) is False

    section = Section(section_index=1, blocks=[eng_block])
    units = resolver.resolve_relationships(section)
    # No VerseUnit should be initiated with an English paragraph as original_script_block_ids
    assert len(units) == 0


def test_defect_5_invocation_prayers_not_collapsed() -> None:
    """Defect 5: Invocation prayers and ritual mantras must NOT collapse into 1 giant VerseUnit."""
    m1 = make_block(BlockType.VERSE_DEVANAGARI, "ॐ तुलसीदासाय नमः।", seq=1)
    t1 = make_block(
        BlockType.TRANSLATION,
        "“Obeisance to you, O Tulasīdāsa ! Taking your seat, accept this adoration.”",
        seq=2,
    )

    m2 = make_block(BlockType.VERSE_DEVANAGARI, "ॐ वाल्मीकाय नमः।", seq=3)
    t2 = make_block(
        BlockType.TRANSLATION, "“Obeisance to you, O Vālmīki ! Bestow your blessings.”", seq=4
    )

    ritual_prose = make_block(
        BlockType.PARAGRAPH,
        "Karanyāsa consists in invoking and installing typical Mantras on the various fingers.",
        seq=5,
    )

    section = Section(section_index=1, blocks=[m1, t1, m2, t2, ritual_prose])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 2
    assert units[0].original_script_block_ids == [m1.id]
    assert units[0].translation_block_ids == [t1.id]
    assert units[1].original_script_block_ids == [m2.id]
    assert units[1].translation_block_ids == [t2.id]
    # Ritual prose paragraph must NOT be swallowed into either mantra unit
    for u in units:
        assert ritual_prose.id not in u.translation_block_ids


def test_defect_6_legitimate_composite_translation_local_proximity() -> None:
    """Defect 6: Legitimate composite translation (1-4) binds strictly to local verses 1-4."""
    v1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ0ó एक बार भूपति मन माहीं। भै गलानि मोरें सुत नाहीं॥ 1॥",
        seq=1,
    )
    v2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "निज दुख सुख सब गुरहि सुनायउ। कहि बसिष्ठ बहु बिधि समुझायउ॥ 2॥",
        seq=2,
    )
    v3 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "सृंगी रिषिहि बसिष्ठ बोलावा। पुत्रकाम सुभ जग्य करावा॥ 3॥",
        seq=3,
    )
    v4 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "जो बसिष्ठ कछु हृदयँ बिचारा। सकल काजु भा सिद्ध तुम्हारा॥ 4॥",
        seq=4,
    )
    comp_trans = make_block(
        BlockType.TRANSLATION,
        "Chaupais (1-4): One day the king was sad at heart that he had no son...",
        seq=5,
    )

    section = Section(section_index=1, blocks=[v1, v2, v3, v4, comp_trans])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 4
    for u in units:
        assert u.translation_block_ids == [comp_trans.id]
        assert "composite_translation_anchor" in u.confidence.provenance_rules
        assert u.is_complete is True
        assert u.confidence.routing_action == RoutingAction.AUTO_ACCEPTED


def test_chhanda_stanzas_meter_inheritance() -> None:
    """Verify that subsequent Chhanda stanzas inherit CHHANDA from the opening stanza."""
    chh1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "छं०—भए प्रगट कृपाला दीनदयाला कौसल्या हितकारी। अद्भुत रूप बिचारी॥ 1॥",
        seq=1,
    )
    t1 = make_block(
        BlockType.TRANSLATION,
        "(1) The gracious Lord appeared, compassionate to the lowly...",
        seq=2,
    )
    chh2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "कह दुइ कर जोरी अस्तुति तोरी केहि बिधि करौं अनंता। भयउ प्रगट श्रीकंता॥ 2॥",
        seq=3,
    )
    t2 = make_block(
        BlockType.TRANSLATION,
        "(2) Folding her hands the mother said, How would I adore You...",
        seq=4,
    )
    chh3 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "ब्रह्मांड निकाया निर्मित माया रोम रोम प्रति बेद कहै। जेहि प्रकार सुत प्रेम लहै॥ 3॥",
        seq=5,
    )
    t3 = make_block(
        BlockType.TRANSLATION,
        "(3) Innumerable universes are created by Your delusion...",
        seq=6,
    )
    doha192 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो०—निज इच्छा निर्मित तनु माया गुन गो पार॥ 192॥",
        seq=7,
    )
    t_doha = make_block(
        BlockType.TRANSLATION,
        "(192) The Lord whose body is assumed by His own will...",
        seq=8,
    )

    section = Section(section_index=1, blocks=[chh1, t1, chh2, t2, chh3, t3, doha192, t_doha])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 4
    assert units[0].unit_type == VerseUnitType.CHHANDA
    assert units[1].unit_type == VerseUnitType.CHHANDA  # Inherited
    assert units[2].unit_type == VerseUnitType.CHHANDA  # Inherited
    assert units[3].unit_type == VerseUnitType.DOHA  # Not inherited, has explicit doha marker


def test_unique_canonical_ids_with_governing_doha() -> None:
    """Verify that Chaupais and Chhandas receive unique IDs scoped by their governing Doha."""
    doha189 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो०—तब अदृस्य भए पावक सकल सभहि समुझाइ॥ 189॥",
        seq=1,
    )
    c1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ०—तबहिं रायँ प्रिय नारि बोलाईं॥ 1॥",
        seq=2,
    )
    doha190 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो०—जोग लगन ग्रह बार तिथि सकल भए अनुकूल॥ 190॥",
        seq=3,
    )
    c2 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "चौ०—नौमी तिथि मधु मास पुनीता॥ 1॥",
        seq=4,
    )
    doha191 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "दो०—सुर समूह बिनती करि पहुँचे निज निज धाम॥ 191॥",
        seq=5,
    )
    chh1 = make_block(
        BlockType.VERSE_DEVANAGARI,
        "छं०—भए प्रगट कृपाला दीनदयाला कौसल्या हितकारी॥ 1॥",
        seq=6,
    )

    section = Section(section_index=1, blocks=[doha189, c1, doha190, c2, doha191, chh1])
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 6
    assert units[0].canonical_id == "1.189"
    assert units[1].canonical_id == "1.190.1"  # Chaupai 1 belongs to target Doha 190
    assert units[2].canonical_id == "1.190"
    assert units[3].canonical_id == "1.191.1"  # Chaupai 1 belongs to target Doha 191
    assert units[4].canonical_id == "1.191"
    assert units[5].canonical_id == "1.192.chhanda.1"  # Chhanda 1 belongs to target Doha 192


def test_convention_a_target_doha_anchoring_synthetic() -> None:
    """Verify Convention A anchoring for Chaupais and Chhandas:
    - Chaupais between Doha N and Doha N+1 belong to target Doha N+1.
    - Chhandas following Doha 191 and preceding Doha 192 belong to target Doha 192.
    - Full 19-unit sequence is unique and continuous across page boundaries.
    """
    blocks = [
        # Doha 188
        make_block(BlockType.VERSE_DEVANAGARI, "दो०—कौसल्यादि नारि प्रिय सब आचरन पुनीत॥ 188॥", seq=1),
        # Chaupais leading up to Doha 189
        make_block(BlockType.VERSE_DEVANAGARI, "चौ०—एक बार भूपति मन माहीं॥ 1॥", seq=2),
        make_block(BlockType.VERSE_DEVANAGARI, "निज दुख सुख सब गुरहि सुनायउ॥ 2॥", seq=3),
        make_block(BlockType.VERSE_DEVANAGARI, "सृंगी रिषिहि बसिष्ठ बोलावा॥ 3॥", seq=4),
        make_block(BlockType.VERSE_DEVANAGARI, "जो बसिष्ठ कछु हृदयँ बिचारा॥ 4॥", seq=5),
        # Doha 189
        make_block(BlockType.VERSE_DEVANAGARI, "दो०—तब अदृस्य भए पावक सकल सभहि समुझाइ॥ 189॥", seq=6),
        # Chaupais leading up to Doha 190
        make_block(BlockType.VERSE_DEVANAGARI, "चौ०—तबहिं रायँ प्रिय नारि बोलाईं॥ 1॥", seq=7),
        make_block(BlockType.VERSE_DEVANAGARI, "कैकेई कहँ नृप सो दयऊ॥ 2॥", seq=8),
        make_block(BlockType.VERSE_DEVANAGARI, "एहि बिधि गर्भसहित सब नारी॥ 3॥", seq=9),
        make_block(BlockType.VERSE_DEVANAGARI, "मंदिर महँ सब राजहिं रानीं॥ 4॥", seq=10),
        # Doha 190
        make_block(BlockType.VERSE_DEVANAGARI, "दो०—जोग लगन ग्रह बार तिथि सकल भए अनुकूल॥ 190॥", seq=11),
        # Chaupais leading up to Doha 191
        make_block(BlockType.VERSE_DEVANAGARI, "चौ०—नौमी तिथि मधु मास पुनीता॥ 1॥", seq=12),
        make_block(BlockType.VERSE_DEVANAGARI, "सीतल मंद सुरभि बह बाऊ॥ 2॥", seq=13),
        make_block(BlockType.VERSE_DEVANAGARI, "सो अवसर बिरंचि जब जाना॥ 3॥", seq=14),
        make_block(BlockType.VERSE_DEVANAGARI, "बरषहिं सुमन सुअंजुलि साजी॥ 4॥", seq=15),
        # Doha 191
        make_block(BlockType.VERSE_DEVANAGARI, "दो०—सुर समूह बिनती करि पहुँचे निज निज धाम॥ 191॥", seq=16),
        # Chhandas leading up to Doha 192
        make_block(BlockType.VERSE_DEVANAGARI, "छं०—भए प्रगट कृपाला दीनदयाला कौसल्या हितकारी॥ 1॥", seq=17),
        make_block(BlockType.VERSE_DEVANAGARI, "कह दुइ कर जोरी अस्तुति तोरी केहि बिधि करौं अनंता॥ 2॥", seq=18),
        make_block(BlockType.VERSE_DEVANAGARI, "ब्रह्मांड निकाया निर्मित माया रोम रोम प्रति बेद कहै॥ 3॥", seq=19),
    ]
    # Set page metadata across page boundaries 215 -> 216 -> 217 -> 218
    for b in blocks[0:5]:
        b.metadata["page"] = 215
    for b in blocks[5:11]:
        b.metadata["page"] = 216
    for b in blocks[11:16]:
        b.metadata["page"] = 217
    for b in blocks[16:19]:
        b.metadata["page"] = 218

    section = Section(section_index=1, blocks=blocks)
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 19

    expected_ids = [
        "1.188",
        "1.189.1",
        "1.189.2",
        "1.189.3",
        "1.189.4",
        "1.189",
        "1.190.1",
        "1.190.2",
        "1.190.3",
        "1.190.4",
        "1.190",
        "1.191.1",
        "1.191.2",
        "1.191.3",
        "1.191.4",
        "1.191",
        "1.192.chhanda.1",
        "1.192.chhanda.2",
        "1.192.chhanda.3",
    ]

    actual_ids = [u.canonical_id for u in units]
    assert actual_ids == expected_ids
    assert len(set(actual_ids)) == 19

    # Unit types check
    assert units[0].unit_type == VerseUnitType.DOHA
    for u in units[1:5]:
        assert u.unit_type == VerseUnitType.CHAUPAI
    assert units[5].unit_type == VerseUnitType.DOHA
    for u in units[6:10]:
        assert u.unit_type == VerseUnitType.CHAUPAI
    assert units[10].unit_type == VerseUnitType.DOHA
    for u in units[11:15]:
        assert u.unit_type == VerseUnitType.CHAUPAI
    assert units[15].unit_type == VerseUnitType.DOHA
    for u in units[16:19]:
        assert u.unit_type == VerseUnitType.CHHANDA


def test_convention_a_pages_215_218_complete_sequence_and_uniqueness() -> None:
    """Verify Convention A across pages 215-218 of Ramcharita_Manas_Gita_Press.pdf:
    - 19 VerseUnits in exact continuous sequence across page boundaries (215->216->217->218).
    - Uniqueness of every canonical ID.
    - Correct target-Doha anchoring for Chaupai and Chhanda.
    """
    from pathlib import Path

    from vedic_translator.document_processor.extractors.pdf import PDFExtractor

    pdf_path = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not pdf_path.exists():
        pytest.skip("Test book PDF not available in workspace")

    doc = PDFExtractor().extract(pdf_path)
    blocks_215_218 = [
        b
        for ch in doc.chapters
        for s in ch.sections
        for b in s.blocks
        if b.metadata.get("page") in {215, 216, 217, 218}
    ]

    section = Section(section_index=1, blocks=blocks_215_218)
    resolver = RuleBasedRelationshipResolver(default_profile=RAMCHARITA_MANAS_PROFILE)
    units = resolver.resolve_relationships(section)

    assert len(units) == 19
    actual_ids = [u.canonical_id for u in units]

    expected_ids = [
        "1.188",
        "1.189.1",
        "1.189.2",
        "1.189.3",
        "1.189.4",
        "1.189",
        "1.190.1",
        "1.190.2",
        "1.190.3",
        "1.190.4",
        "1.190",
        "1.191.1",
        "1.191.2",
        "1.191.3",
        "1.191.4",
        "1.191",
        "1.192.chhanda.1",
        "1.192.chhanda.2",
        "1.192.chhanda.3",
    ]
    assert actual_ids == expected_ids
    assert len(set(actual_ids)) == 19
