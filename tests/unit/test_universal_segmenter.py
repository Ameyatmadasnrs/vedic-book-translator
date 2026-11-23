"""Unit and regression tests for Phase 1.2 Stage 1: Universal English Structure & Content Types.

Verifies:
1. Classification of all universal content types:
   - HEADING, SUBHEADING, PARAGRAPH, BLOCKQUOTE / QUOTE, EPIGRAPH,
     LIST_ITEM, TABLE, FOOTNOTE, THEMATIC_BREAK, CAPTION.
2. Ambiguous headings (short lines with/without terminal punctuation, titles).
3. Quoted paragraphs and attribution lines.
4. Lists (bulleted, numbered, lettered).
5. Footnotes (DOCX style, EPUB tag, bracketed anchor, PDF footer bbox).
6. Mixed English and Sanskrit inline terms (ensuring prose is NOT classified as a verse).
7. Deep immutability of raw Document AST when modifying enriched AST metadata.
8. Deterministic scoring and bounded confidence [0.0, 1.0].
9. Backward compatibility of all existing BlockType enum values.
10. DocumentIntegrityValidator invariant checks (uniqueness, sequence continuity, confidence range).
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import docx
import pymupdf as fitz
import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from ebooklib import epub

from vedic_translator.core.exceptions import ReferentialIntegrityError
from vedic_translator.core.models import (
    Block,
    BlockType,
    Chapter,
    Document,
    DocumentMetadata,
    Section,
)
from vedic_translator.document_processor.extractors import (
    DOCXExtractor,
    EPUBExtractor,
    PDFExtractor,
)
from vedic_translator.document_processor.segmenter import (
    BlockContext,
    ContentClassifier,
    DocumentIntegrityValidator,
    SegmentationProfile,
    SegmenterPipeline,
)

FROZEN_TIME = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    """Fixed deterministic clock for testing."""
    return FROZEN_TIME


@pytest.fixture
def classifier() -> ContentClassifier:
    """Standard ContentClassifier with fixed clock."""
    return ContentClassifier(clock=fixed_clock)


@pytest.fixture
def sample_raw_doc() -> Document:
    """A sample raw document as emitted by Phase 1.1 extractors."""
    blocks = [
        Block(
            type=BlockType.HEADING,
            source_text="Chapter 1: The Spiritual Quest",
            sequence_index=0,
            metadata={"page": 1, "bbox": [50.0, 50.0, 400.0, 72.0], "font_size": 16.0},
        ),
        Block(
            type=BlockType.PARAGRAPH,
            source_text="“Know thyself is the ancient motto.”\n— Ralph Waldo Emerson",
            sequence_index=1,
            metadata={"page": 1, "bbox": [72.0, 90.0, 350.0, 120.0], "font_size": 10.0},
        ),
        Block(
            type=BlockType.PARAGRAPH,
            source_text=(
                "Philosophy is not a theoretical speculation, but a practical way of living. "
                "The journey of self-realization begins with inquiry into the nature of consciousness."
            ),
            sequence_index=2,
            metadata={"page": 1, "bbox": [50.0, 130.0, 500.0, 180.0], "font_size": 11.0},
        ),
        Block(
            type=BlockType.PARAGRAPH,
            source_text="* * *",
            sequence_index=3,
            metadata={"page": 1, "bbox": [250.0, 200.0, 290.0, 212.0]},
        ),
        Block(
            type=BlockType.PARAGRAPH,
            source_text="1. Self-awareness and meditation\n2. Ethical discipline",
            sequence_index=4,
            metadata={"page": 1, "bbox": [50.0, 230.0, 400.0, 260.0], "font_size": 11.0},
        ),
    ]
    sec = Section(section_index=1, heading="Chapter 1: The Spiritual Quest", blocks=blocks)
    ch = Chapter(chapter_index=1, title="Chapter 1: The Spiritual Quest", sections=[sec])
    return Document(
        metadata=DocumentMetadata(title="The Spiritual Quest", author="A. C. Bhaktivedanta"),
        chapters=[ch],
    )


# -----------------------------------------------------------------------------
# 1. Backward Compatibility of BlockType Enum Values
# -----------------------------------------------------------------------------


def test_block_type_backward_compatibility() -> None:
    """Verify that all Phase 1.1 BlockType enum values remain valid and unchanged."""
    phase_1_1_values = [
        "VERSE_DEVANAGARI",
        "VERSE_IAST",
        "SYNONYMS",
        "TRANSLATION",
        "PURPORT",
        "HEADING",
        "SUBHEADING",
        "PARAGRAPH",
        "FOOTNOTE",
        "QUOTE",
    ]
    for val in phase_1_1_values:
        enum_member = BlockType(val)
        assert enum_member.value == val

    # Verify newly added universal types exist
    universal_values = [
        "BLOCKQUOTE",
        "EPIGRAPH",
        "LIST_ITEM",
        "TABLE",
        "THEMATIC_BREAK",
        "CAPTION",
    ]
    for val in universal_values:
        enum_member = BlockType(val)
        assert enum_member.value == val


# -----------------------------------------------------------------------------
# 2. Universal Content Type Classification Unit Tests
# -----------------------------------------------------------------------------


def test_classify_thematic_break(classifier: ContentClassifier) -> None:
    """Test recognition of thematic breaks / dividers."""
    break_samples = ["***", "* * *", "---", "- - -", "___", "• • •", "–––"]
    for text in break_samples:
        block = Block(type=BlockType.PARAGRAPH, source_text=text)
        res = classifier.classify(block)
        assert res.block_type == BlockType.THEMATIC_BREAK
        assert res.confidence >= 0.90
        assert 0.0 <= res.confidence <= 1.0


def test_classify_footnote(classifier: ContentClassifier) -> None:
    """Test recognition of footnotes via style, tags, anchors, and PDF geometry."""
    # 1. DOCX style
    b_docx = Block(
        type=BlockType.PARAGRAPH,
        source_text="1. See Bhagavad-gita As It Is, Chapter 2.",
        metadata={"style_name": "Footnote Text"},
    )
    assert classifier.classify(b_docx).block_type == BlockType.FOOTNOTE

    # 2. EPUB tag
    b_epub = Block(
        type=BlockType.PARAGRAPH,
        source_text="Explanatory commentary on ancient texts.",
        metadata={"tag": "aside", "classes": ["footnote"]},
    )
    assert classifier.classify(b_epub).block_type == BlockType.FOOTNOTE

    # 3. Text pattern anchor [1]
    b_text = Block(
        type=BlockType.PARAGRAPH,
        source_text="[^12] Translation based on Sanskrit commentary of Sridhara Swami.",
    )
    assert classifier.classify(b_text).block_type == BlockType.FOOTNOTE

    # 4. PDF bottom-of-page layout geometry
    b_pdf = Block(
        type=BlockType.PARAGRAPH,
        source_text="14. Additional historical notes regarding Kurukshetra.",
        metadata={"bbox": [54.0, 720.0, 500.0, 735.0], "font_size": 8.5},
    )
    assert classifier.classify(b_pdf).block_type == BlockType.FOOTNOTE


def test_classify_table(classifier: ContentClassifier) -> None:
    """Test recognition of markdown tables, tab-delimited columns, and native tags."""
    # 1. Markdown table
    md_table = "| Name | Role | Location |\n|---|---|---|\n| Arjuna | Warrior | Kurukshetra |"
    b_md = Block(type=BlockType.PARAGRAPH, source_text=md_table)
    assert classifier.classify(b_md).block_type == BlockType.TABLE

    # 2. Tab-delimited table
    tab_table = "Chapter\tVerses\tFocus\n1\t47\tLamentation\n2\t72\tGita Summary"
    b_tab = Block(type=BlockType.PARAGRAPH, source_text=tab_table)
    assert classifier.classify(b_tab).block_type == BlockType.TABLE

    # 3. EPUB table tag
    b_tag = Block(
        type=BlockType.PARAGRAPH,
        source_text="Cell content",
        metadata={"tag": "table"},
    )
    assert classifier.classify(b_tag).block_type == BlockType.TABLE


def test_classify_list_item(classifier: ContentClassifier) -> None:
    """Test recognition of bulleted and numbered list items."""
    bullets = [
        "• First principle of devotional service",
        "- Acceptance of a spiritual master",
        "* Inquiring into eternal truth",
        "1. Hearing the transcendental sound",
        "a) Chanting with devotion",
        "(i) Remembering the Supreme Lord",
    ]
    for text in bullets:
        b = Block(type=BlockType.PARAGRAPH, source_text=text)
        res = classifier.classify(b)
        assert res.block_type == BlockType.LIST_ITEM
        assert res.confidence >= 0.85

    # DOCX List style
    b_docx = Block(
        type=BlockType.PARAGRAPH,
        source_text="Sravanam, kirtanam, smaranam",
        metadata={"style_name": "List Bullet"},
    )
    assert classifier.classify(b_docx).block_type == BlockType.LIST_ITEM


def test_classify_caption(classifier: ContentClassifier) -> None:
    """Test recognition of figure and table captions."""
    captions = [
        "Figure 1: Map of ancient Bharatavarsa and the Kurukshetra battlefield.",
        "Fig. 2. Archeological layout of Hastinapura.",
        "Table 3: Comparison of the three modes of material nature.",
        "Plate 4: Sri Krishna speaking to Arjuna on the chariot.",
    ]
    for text in captions:
        b = Block(type=BlockType.PARAGRAPH, source_text=text)
        res = classifier.classify(b)
        assert res.block_type == BlockType.CAPTION
        assert res.confidence >= 0.90


def test_classify_epigraph(classifier: ContentClassifier) -> None:
    """Test recognition of chapter opening epigraphs."""
    heading_block = Block(
        type=BlockType.HEADING,
        source_text="Chapter 1: The Nature of Being",
    )
    epigraph_block = Block(
        type=BlockType.PARAGRAPH,
        source_text="“Truth is one, though the wise call it by many names.”\n— Rig Veda",
    )
    context = BlockContext(
        preceding_block=heading_block,
        block_index_in_section=1,
        total_blocks_in_section=5,
    )
    res = classifier.classify(epigraph_block, context=context)
    assert res.block_type == BlockType.EPIGRAPH
    assert res.confidence >= 0.85


def test_classify_blockquote(classifier: ContentClassifier) -> None:
    """Test recognition of blockquotes via markdown, DOCX styles, and layout indent."""
    # 1. Markdown quote
    b_md = Block(
        type=BlockType.PARAGRAPH,
        source_text="> The unexamined life is not worth living, as Socrates taught.",
    )
    assert classifier.classify(b_md).block_type == BlockType.BLOCKQUOTE

    # 2. DOCX quote style
    b_docx = Block(
        type=BlockType.PARAGRAPH,
        source_text="Devotional service is the ultimate objective of human existence.",
        metadata={"style_name": "Quote"},
    )
    assert classifier.classify(b_docx).block_type == BlockType.BLOCKQUOTE

    # 3. PDF indent (bbox x0 >= 72pt)
    b_pdf = Block(
        type=BlockType.PARAGRAPH,
        source_text="A dedicated excerpt indented from the standard margins.",
        metadata={"bbox": [75.0, 100.0, 450.0, 140.0]},
    )
    assert classifier.classify(b_pdf).block_type == BlockType.BLOCKQUOTE


def test_classify_headings_and_subheadings(classifier: ContentClassifier) -> None:
    """Test recognition of HEADING vs SUBHEADING across formats."""
    # 1. DOCX Heading 1 vs Heading 2
    h1 = Block(
        type=BlockType.PARAGRAPH, source_text="Introduction", metadata={"style_name": "Heading 1"}
    )
    h2 = Block(
        type=BlockType.PARAGRAPH,
        source_text="Historical Background",
        metadata={"style_name": "Heading 2"},
    )
    assert classifier.classify(h1).block_type == BlockType.HEADING
    assert classifier.classify(h2).block_type == BlockType.SUBHEADING

    # 2. Markdown # vs ## vs ###
    md_h1 = Block(type=BlockType.PARAGRAPH, source_text="# Chapter 2: Contents of the Gita")
    md_h3 = Block(type=BlockType.PARAGRAPH, source_text="### Section 2.1: The Eternal Soul")
    assert classifier.classify(md_h1).block_type == BlockType.HEADING
    assert classifier.classify(md_h3).block_type == BlockType.SUBHEADING

    # 3. EPUB tags
    epub_h1 = Block(type=BlockType.PARAGRAPH, source_text="Preface", metadata={"tag": "h1"})
    epub_h4 = Block(
        type=BlockType.PARAGRAPH, source_text="Terminology Overview", metadata={"tag": "h4"}
    )
    assert classifier.classify(epub_h1).block_type == BlockType.HEADING
    assert classifier.classify(epub_h4).block_type == BlockType.SUBHEADING

    # 4. Text regex (Chapter 1)
    regex_ch = Block(type=BlockType.PARAGRAPH, source_text="Chapter 1: Observing the Armies")
    assert classifier.classify(regex_ch).block_type == BlockType.HEADING


# -----------------------------------------------------------------------------
# 3. Ambiguity & Safeguard Tests: Mixed English/Sanskrit & Prose Veto
# -----------------------------------------------------------------------------


def test_mixed_english_sanskrit_is_not_classified_as_verse(classifier: ContentClassifier) -> None:
    """Verify that English prose with inline Sanskrit is classified as PARAGRAPH, never verse."""
    prose_with_sanskrit = (
        "The concept of dharma (धर्म) implies one's constitutional nature and duty, "
        "which can never be separated from the living entity, just as heat cannot be separated from fire."
    )
    block = Block(type=BlockType.PARAGRAPH, source_text=prose_with_sanskrit)
    res = classifier.classify(block)

    # In Stage 1, this must be PARAGRAPH
    assert res.block_type == BlockType.PARAGRAPH
    assert res.block_type != BlockType.VERSE_DEVANAGARI
    assert res.block_type != BlockType.VERSE_IAST
    assert res.confidence >= 0.85


def test_ambiguous_short_line_prose_veto(classifier: ContentClassifier) -> None:
    """Verify that short lines with multiple verbs are not misclassified as headings."""
    # A complete sentence that happens to be short
    short_sentence = "It was explained that he is alive."
    block = Block(type=BlockType.PARAGRAPH, source_text=short_sentence)
    res = classifier.classify(block)
    # Ends with period, contains finite verbs 'was', 'is' -> PARAGRAPH, not HEADING
    assert res.block_type == BlockType.PARAGRAPH


def test_configurable_prose_veto_behavior() -> None:
    """Verify that prose-veto can be toggled via SegmentationProfile."""
    # Short title-cased sentence with 2 verbs
    text = "Truth Is What Remains"

    # Profile with prose-veto enabled (default)
    prof_default = SegmentationProfile(enable_prose_veto=True)
    clf_default = ContentClassifier(profile=prof_default, clock=fixed_clock)
    res1 = clf_default.classify(Block(type=BlockType.PARAGRAPH, source_text=text))
    # 'is', 'remains' are verbs -> prose veto prevents heading
    assert res1.block_type == BlockType.PARAGRAPH

    # Profile with prose-veto disabled
    prof_disabled = SegmentationProfile(enable_prose_veto=False)
    clf_disabled = ContentClassifier(profile=prof_disabled, clock=fixed_clock)
    res2 = clf_disabled.classify(Block(type=BlockType.PARAGRAPH, source_text=text))
    # Without veto, capitalized short text without period can qualify as SUBHEADING
    assert res2.block_type == BlockType.SUBHEADING


# -----------------------------------------------------------------------------
# 4. Deterministic Scoring and Bounded Confidence [0.0, 1.0]
# -----------------------------------------------------------------------------


def test_deterministic_scoring_and_confidence_bounds(classifier: ContentClassifier) -> None:
    """Verify that all confidence scores are strictly bounded in [0.0, 1.0] and repeatable."""
    test_texts = [
        "***",
        "# Major Heading",
        "1. Numbered item in a list",
        "> A famous blockquote citation",
        "Figure 1: Ancient map of Mathura.",
        "[1] A critical scholarly footnote.",
        "Standard narrative prose sentence that extends across several clauses.",
    ]
    for text in test_texts:
        b = Block(type=BlockType.PARAGRAPH, source_text=text)
        res1 = classifier.classify(b)
        res2 = classifier.classify(b)

        # 1. Exact deterministic identity
        assert res1.block_type == res2.block_type
        assert res1.confidence == res2.confidence
        assert res1.provenance.applied_at == res2.provenance.applied_at
        assert res1.provenance.rule_name == res2.provenance.rule_name

        # 2. Strict mathematical bounds
        assert 0.0 <= res1.confidence <= 1.0
        for alt in res1.alternatives:
            assert 0.0 <= alt.confidence <= 1.0


# -----------------------------------------------------------------------------
# 5. Deep Immutability of Raw Document AST
# -----------------------------------------------------------------------------


def test_raw_ast_deep_immutability(sample_raw_doc: Document) -> None:
    """Test proving that modifying enriched metadata cannot modify the raw AST."""
    # 1. Record raw document state snapshot
    raw_snapshot = sample_raw_doc.model_dump_json()
    orig_bbox = sample_raw_doc.chapters[0].sections[0].blocks[0].metadata["bbox"]

    # 2. Run segmentation pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    enriched_doc = pipeline.segment(sample_raw_doc)

    # 3. Deliberately tamper with enriched document AST
    first_block = enriched_doc.chapters[0].sections[0].blocks[0]
    first_block.metadata["bbox"][0] = 9999.0
    first_block.metadata["tamper_key"] = "malicious_injection"
    first_block.type = BlockType.THEMATIC_BREAK

    # 4. Assert that raw document was NOT mutated in any way
    assert sample_raw_doc.model_dump_json() == raw_snapshot
    assert "tamper_key" not in sample_raw_doc.chapters[0].sections[0].blocks[0].metadata
    assert sample_raw_doc.chapters[0].sections[0].blocks[0].metadata["bbox"] == orig_bbox
    assert sample_raw_doc.chapters[0].sections[0].blocks[0].type == BlockType.HEADING


# -----------------------------------------------------------------------------
# 6. Pipeline Integration and Preservation of Source Text and IDs
# -----------------------------------------------------------------------------


def test_segmenter_pipeline_preserves_identities_and_reading_order(
    sample_raw_doc: Document,
) -> None:
    """Verify that SegmenterPipeline preserves block IDs, source_text, and sequence indices."""
    pipeline = SegmenterPipeline(clock=fixed_clock)
    enriched_doc = pipeline.segment(sample_raw_doc)

    raw_blocks = [b for ch in sample_raw_doc.chapters for s in ch.sections for b in s.blocks]
    enriched_blocks = [b for ch in enriched_doc.chapters for s in ch.sections for b in s.blocks]

    assert len(raw_blocks) == len(enriched_blocks)

    for raw_b, enriched_b in zip(raw_blocks, enriched_blocks, strict=True):
        # 1. Identity preservation
        assert raw_b.id == enriched_b.id
        # 2. Verbatim source_text preservation
        assert raw_b.source_text == enriched_b.source_text
        # 3. Sequence index preservation
        assert raw_b.sequence_index == enriched_b.sequence_index
        # 4. Provenance populated
        assert enriched_b.provenance is not None
        assert 0.0 <= enriched_b.provenance.confidence <= 1.0

    # Check classifications in sample
    assert enriched_blocks[0].type == BlockType.HEADING
    assert enriched_blocks[1].type == BlockType.EPIGRAPH
    assert enriched_blocks[2].type == BlockType.PARAGRAPH
    assert enriched_blocks[3].type == BlockType.THEMATIC_BREAK
    assert enriched_blocks[4].type == BlockType.LIST_ITEM


# -----------------------------------------------------------------------------
# 7. DocumentIntegrityValidator Tests
# -----------------------------------------------------------------------------


def test_document_integrity_validator_detects_violations(sample_raw_doc: Document) -> None:
    """Test DocumentIntegrityValidator catches duplicate IDs, broken sequence, and unbounded scores."""
    validator = DocumentIntegrityValidator(raise_on_error=True)

    # 1. Valid document passes
    report = validator.validate(sample_raw_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 5

    # 2. Duplicate Block ID raises ReferentialIntegrityError
    corrupt_doc = sample_raw_doc.model_copy(deep=True)
    duplicate_id = corrupt_doc.chapters[0].sections[0].blocks[0].id
    corrupt_doc.chapters[0].sections[0].blocks[1].id = duplicate_id

    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(corrupt_doc)
    assert "Duplicate Block ID detected" in str(exc_info.value)

    # 3. Broken sequence index monotonicity
    corrupt_seq = sample_raw_doc.model_copy(deep=True)
    corrupt_seq.chapters[0].sections[0].blocks[2].sequence_index = 0
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(corrupt_seq)
    assert "Discontinuous sequence_index" in str(exc_info.value)

    # 4. Duplicate relationship references
    corrupt_rel = sample_raw_doc.model_copy(deep=True)
    shared_unit_id = uuid4()
    corrupt_rel.chapters[0].sections[0].blocks[0].verse_unit_ids = [shared_unit_id, shared_unit_id]
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validator.validate(corrupt_rel)
    assert "Duplicate verse_unit_ids" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 8. Edge-Case and Format Extractor Integration Tests (Stage 1.1 Refinement)
# -----------------------------------------------------------------------------


def test_empty_document_segmentation() -> None:
    """Verify that an empty Document is safely handled by SegmenterPipeline and validator."""
    empty_doc = Document(
        metadata=DocumentMetadata(title="Empty Treatise", author="Unknown"),
        chapters=[],
    )
    pipeline = SegmenterPipeline(clock=fixed_clock)
    enriched_doc = pipeline.segment(empty_doc)

    assert enriched_doc.id == empty_doc.id
    assert enriched_doc.metadata.title == "Empty Treatise"
    assert len(enriched_doc.chapters) == 0
    assert enriched_doc.total_blocks() == 0

    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(enriched_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 0
    assert any("contains no chapters" in w for w in report.warnings)


def test_whitespace_only_block_handling(classifier: ContentClassifier) -> None:
    """Verify that whitespace-only blocks do not cause crashes and preserve exact characters."""
    raw_block = Block(
        type=BlockType.PARAGRAPH,
        source_text="   \n\t  \r\n",
        sequence_index=0,
        metadata={"custom_flag": "test"},
    )
    classification = classifier.classify(raw_block)
    assert classification.block_type == BlockType.PARAGRAPH
    assert 0.0 <= classification.provenance.confidence <= 1.0

    doc = Document(
        metadata=DocumentMetadata(title="Whitespace Doc"),
        chapters=[
            Chapter(
                chapter_index=1,
                title="Ch1",
                sections=[Section(section_index=1, heading=None, blocks=[raw_block])],
            )
        ],
    )
    pipeline = SegmenterPipeline(clock=fixed_clock)
    enriched_doc = pipeline.segment(doc)

    enriched_block = enriched_doc.chapters[0].sections[0].blocks[0]
    assert enriched_block.source_text == "   \n\t  \r\n"
    assert enriched_block.type == BlockType.PARAGRAPH
    assert enriched_block.provenance is not None
    assert 0.0 <= enriched_block.provenance.confidence <= 1.0


def test_end_to_end_docx_extractor_to_segmenter_integration(tmp_path: Path) -> None:
    """Verify end-to-end extraction from DOCX with style metadata through SegmenterPipeline."""
    docx_file = tmp_path / "integration_test.docx"
    doc_builder = docx.Document()
    doc_builder.core_properties.title = "Vedic Philosophy"
    doc_builder.core_properties.author = "Vyasa"

    # 1. Heading 1
    doc_builder.add_heading("Chapter 1: The Cosmic Vision", level=1)
    # 2. Body Paragraph
    doc_builder.add_paragraph("The cosmic manifestation is an expansion of the supreme energy.")
    # 3. Bullet list item
    doc_builder.add_paragraph("First principle of perception", style="List Bullet")
    # 4. Table
    table = doc_builder.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Element"
    table.rows[0].cells[1].text = "Quality"
    table.rows[1].cells[0].text = "Earth"
    table.rows[1].cells[1].text = "Smell"

    doc_builder.save(str(docx_file))

    # Extract via DOCXExtractor
    extractor = DOCXExtractor()
    extracted_doc = extractor.extract(docx_file)

    # Verify extractor preserved formatting metadata
    all_blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(all_blocks) == 5

    # Check heading metadata
    assert all_blocks[0].metadata.get("style_name") == "Heading 1"
    assert all_blocks[0].metadata.get("heading_level") == 1

    # Check body metadata
    assert all_blocks[1].metadata.get("style_name") == "Normal"

    # Check list metadata
    assert all_blocks[2].metadata.get("is_list") is True

    # Check table row metadata
    assert all_blocks[3].metadata.get("is_table_row") is True
    assert all_blocks[3].metadata.get("cells_count") == 2
    assert all_blocks[3].metadata.get("row_index") == 0
    assert all_blocks[3].metadata.get("total_rows") == 2
    assert all_blocks[3].metadata.get("cells") == ["Element", "Quality"]
    assert all_blocks[3].metadata.get("is_header_row") is False
    assert all_blocks[3].metadata.get("table_id") == all_blocks[4].metadata.get("table_id")

    # Segment via SegmenterPipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented_doc = pipeline.segment(extracted_doc)

    seg_blocks = [b for ch in segmented_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(seg_blocks) == 5

    assert seg_blocks[0].type == BlockType.HEADING
    assert seg_blocks[1].type == BlockType.PARAGRAPH
    assert seg_blocks[2].type == BlockType.LIST_ITEM
    assert seg_blocks[3].type == BlockType.TABLE
    assert seg_blocks[4].type == BlockType.TABLE

    # Validate integrity
    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 5


def test_end_to_end_epub_extractor_to_segmenter_integration(tmp_path: Path) -> None:
    """Verify end-to-end extraction from EPUB with semantic HTML tags through SegmenterPipeline."""
    epub_file = tmp_path / "integration_book.epub"
    book = epub.EpubBook()
    book.set_identifier("vedic-pipeline-epub-1")
    book.set_title("Bhagavad Gita Study")
    book.set_language("en")
    book.add_author("Srila Prabhupada")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<h1>Chapter 1: Observing the Armies</h1>"
        "<h2>Section A: The Dilemma</h2>"
        "<p>Arjuna looked upon both sides of the battlefield with deep compassion.</p>"
        "<blockquote>“O Krishna, seeing my kinsmen arrayed for battle, my limbs fail me.”</blockquote>"
        "<ul>"
        "<li>Grief over family destruction</li>"
        "<li>Fear of sinful reaction</li>"
        "</ul>"
        "</body></html>"
    )
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    # Extract via EPUBExtractor
    extractor = EPUBExtractor()
    extracted_doc = extractor.extract(epub_file)

    # Verify extractor preserved HTML semantic metadata
    all_blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(all_blocks) == 6

    assert all_blocks[0].metadata.get("tag") == "h1"
    assert all_blocks[0].metadata.get("heading_level") == 1
    assert all_blocks[1].metadata.get("tag") == "h2"
    assert all_blocks[1].metadata.get("heading_level") == 2
    assert all_blocks[2].metadata.get("tag") == "p"
    assert all_blocks[3].metadata.get("tag") == "blockquote"
    assert all_blocks[3].metadata.get("is_quote") is True
    assert all_blocks[4].metadata.get("tag") == "li"
    assert all_blocks[4].metadata.get("is_list") is True

    # Segment via SegmenterPipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented_doc = pipeline.segment(extracted_doc)

    seg_blocks = [b for ch in segmented_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(seg_blocks) == 6

    assert seg_blocks[0].type == BlockType.HEADING
    assert seg_blocks[1].type == BlockType.SUBHEADING
    assert seg_blocks[2].type == BlockType.PARAGRAPH
    assert seg_blocks[3].type in (BlockType.BLOCKQUOTE, BlockType.QUOTE)
    assert seg_blocks[4].type == BlockType.LIST_ITEM
    assert seg_blocks[5].type == BlockType.LIST_ITEM

    # Validate integrity
    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 6


def test_end_to_end_pdf_extractor_to_segmenter_integration(tmp_path: Path) -> None:
    """Verify end-to-end extraction from PDF with geometry and font metadata through SegmenterPipeline."""
    pdf_file = tmp_path / "integration_doc.pdf"
    doc = fitz.open()

    page = doc.new_page(width=595, height=842)  # Standard A4
    page.insert_text((50, 72), "Chapter 1: The Living Entity", fontsize=18)
    page.insert_text(
        (50, 150),
        "The spirit soul is indestructible and eternally conscious.",
        fontsize=11,
    )
    # Footnote at the bottom of the page with small font
    page.insert_text(
        (50, 760),
        "[1] Cf. Katha Upanishad 1.2.18 on the eternity of the self.",
        fontsize=8,
    )

    doc.set_metadata({"title": "Soul and Consciousness", "author": "Vedic Scholar"})
    doc.set_toc([[1, "Chapter 1: The Living Entity", 1]])
    doc.save(str(pdf_file))
    doc.close()

    # Extract via PDFExtractor
    extractor = PDFExtractor()
    extracted_doc = extractor.extract(pdf_file)

    all_blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(all_blocks) == 3

    # Heading block has font metadata
    assert all_blocks[0].metadata.get("font_size") == 18.0
    assert all_blocks[0].metadata.get("page") == 1

    # Body block has font metadata
    assert all_blocks[1].metadata.get("font_size") == 11.0
    assert all_blocks[1].metadata.get("page") == 1

    # Footnote block has small font size and page bottom bbox
    assert all_blocks[2].metadata.get("font_size") == 8.0
    bbox_val = all_blocks[2].metadata.get("bbox")
    assert isinstance(bbox_val, list)
    assert bbox_val[1] >= 700.0

    # Segment via SegmenterPipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented_doc = pipeline.segment(extracted_doc)

    seg_blocks = [b for ch in segmented_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(seg_blocks) == 3

    assert seg_blocks[0].type == BlockType.HEADING
    assert seg_blocks[1].type == BlockType.PARAGRAPH
    assert seg_blocks[2].type == BlockType.FOOTNOTE

    # Validate integrity
    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 3


# -----------------------------------------------------------------------------
# 9. Audit Essential Refinement Tests: Nested EPUB & Advanced DOCX Structures
# -----------------------------------------------------------------------------


def test_epub_nested_blockquotes_and_lists_no_duplication(tmp_path: Path) -> None:
    """Verify EPUB nested blockquotes and nested lists are extracted without text duplication."""
    epub_file = tmp_path / "nested_book.epub"
    book = epub.EpubBook()
    book.set_identifier("epub-nested-test")
    book.set_title("Nested Elements Book")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<h1>Chapter 1: The Discourse</h1>"
        "<p>Preamble paragraph.</p>"
        "<blockquote>"
        "  <p>Outer quote line 1.</p>"
        "  <blockquote>"
        "    <p>Inner quote line 2.</p>"
        "  </blockquote>"
        "</blockquote>"
        "<ul>"
        "  <li>Main item 1"
        "    <ul>"
        "      <li>Sub-item 1.1</li>"
        "      <li>Sub-item 1.2</li>"
        "    </ul>"
        "  </li>"
        "  <li>Main item 2</li>"
        "</ul>"
        "<blockquote>Solo quote without inner paragraph</blockquote>"
        "</body></html>"
    )
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    extracted_doc = extractor.extract(epub_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    # Verify count and exact text sequence without duplication
    texts = [b.source_text for b in blocks]
    assert texts == [
        "Chapter 1: The Discourse",
        "Preamble paragraph.",
        "Outer quote line 1.",
        "Inner quote line 2.",
        "Main item 1",
        "Sub-item 1.1",
        "Sub-item 1.2",
        "Main item 2",
        "Solo quote without inner paragraph",
    ]

    # Check blockquote depths and metadata
    assert blocks[2].metadata.get("is_quote") is True
    assert blocks[2].metadata.get("quote_depth") == 1
    assert blocks[2].metadata.get("parent_tag") == "blockquote"

    assert blocks[3].metadata.get("is_quote") is True
    assert blocks[3].metadata.get("quote_depth") == 2

    # Check nested list depths
    assert blocks[4].metadata.get("is_list") is True
    assert blocks[4].metadata.get("list_depth") == 1

    assert blocks[5].metadata.get("is_list") is True
    assert blocks[5].metadata.get("list_depth") == 2

    assert blocks[6].metadata.get("is_list") is True
    assert blocks[6].metadata.get("list_depth") == 2

    assert blocks[7].metadata.get("is_list") is True
    assert blocks[7].metadata.get("list_depth") == 1

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]

    assert seg_blocks[0].type == BlockType.HEADING
    assert seg_blocks[1].type == BlockType.PARAGRAPH
    assert seg_blocks[2].type == BlockType.BLOCKQUOTE
    assert seg_blocks[3].type == BlockType.BLOCKQUOTE
    assert seg_blocks[4].type == BlockType.LIST_ITEM
    assert seg_blocks[5].type == BlockType.LIST_ITEM
    assert seg_blocks[6].type == BlockType.LIST_ITEM
    assert seg_blocks[7].type == BlockType.LIST_ITEM
    assert seg_blocks[8].type == BlockType.BLOCKQUOTE


def test_docx_word_xml_numpr_direct_numbering(tmp_path: Path) -> None:
    """Verify DOCX paragraphs with w:numPr are detected as lists even with Normal style."""
    docx_file = tmp_path / "numpr_test.docx"
    doc_builder = docx.Document()

    # Normal paragraph
    doc_builder.add_paragraph("Introductory text with Normal style.")

    # Paragraph with Normal style but XML w:numPr list formatting
    p_list = doc_builder.add_paragraph("First item with XML numbering.")
    p_pr = p_list._p.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num_id = OxmlElement("w:numId")
    num_id.set(qn("w:val"), "1")
    num_pr.append(ilvl)
    num_pr.append(num_id)
    p_pr.append(num_pr)

    # Nested child item with ilvl=1
    p_nested = doc_builder.add_paragraph("Nested child item with XML numbering.")
    p_pr2 = p_nested._p.get_or_add_pPr()
    num_pr2 = OxmlElement("w:numPr")
    ilvl2 = OxmlElement("w:ilvl")
    ilvl2.set(qn("w:val"), "1")
    num_id2 = OxmlElement("w:numId")
    num_id2.set(qn("w:val"), "1")
    num_pr2.append(ilvl2)
    num_pr2.append(num_id2)
    p_pr2.append(num_pr2)

    doc_builder.save(str(docx_file))

    extractor = DOCXExtractor()
    extracted_doc = extractor.extract(docx_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    assert len(blocks) == 3
    assert blocks[0].metadata.get("numPr") is None
    assert blocks[0].source_text == "Introductory text with Normal style."

    assert blocks[1].metadata.get("is_list") is True
    assert blocks[1].metadata.get("numPr") is True
    assert blocks[1].metadata.get("list_level") == 0
    assert blocks[1].source_text == "First item with XML numbering."

    assert blocks[2].metadata.get("is_list") is True
    assert blocks[2].metadata.get("numPr") is True
    assert blocks[2].metadata.get("list_level") == 1
    assert blocks[2].source_text == "Nested child item with XML numbering."

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]

    assert seg_blocks[0].type == BlockType.PARAGRAPH
    assert seg_blocks[1].type == BlockType.LIST_ITEM
    assert seg_blocks[2].type == BlockType.LIST_ITEM


def test_docx_empty_table_cells_and_multi_paragraph_cells(tmp_path: Path) -> None:
    """Verify DOCX tables preserve empty cells, column count, and multi-paragraph cells."""
    docx_file = tmp_path / "empty_cells_table.docx"
    doc_builder = docx.Document()

    table = doc_builder.add_table(rows=2, cols=3)
    # Row 1: Header
    table.rows[0].cells[0].text = "Col A"
    table.rows[0].cells[1].text = "Col B"
    table.rows[0].cells[2].text = "Col C"

    # Row 2: Middle cell is empty, first cell has 2 paragraphs
    cell_0 = table.rows[1].cells[0]
    cell_0.text = "Para 1"
    cell_0.add_paragraph("Para 2")
    table.rows[1].cells[1].text = ""  # Explicit empty middle cell
    table.rows[1].cells[2].text = "Value C"

    doc_builder.save(str(docx_file))

    extractor = DOCXExtractor()
    extracted_doc = extractor.extract(docx_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    assert len(blocks) == 2
    row0 = blocks[0]
    row1 = blocks[1]

    # Row 0
    assert row0.source_text == "Col A | Col B | Col C"
    assert row0.metadata.get("cells_count") == 3

    # Row 1: empty middle cell preserved, multi-paragraph preserved
    assert row1.source_text == "Para 1\nPara 2 |  | Value C"
    assert row1.metadata.get("cells_count") == 3

    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]
    assert seg_blocks[0].type == BlockType.TABLE
    assert seg_blocks[1].type == BlockType.TABLE


def test_docx_paragraph_table_paragraph_interleaving_order(tmp_path: Path) -> None:
    """Verify DOCX document order preserves paragraph -> table -> paragraph interleaving."""
    docx_file = tmp_path / "interleaved_order.docx"
    doc_builder = docx.Document()

    # 1. Preamble paragraph
    doc_builder.add_paragraph("First paragraph before table.")

    # 2. Table
    table = doc_builder.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Key"
    table.rows[0].cells[1].text = "Value"

    # 3. Subsequent paragraph
    doc_builder.add_paragraph("Second paragraph after table.")

    doc_builder.save(str(docx_file))

    extractor = DOCXExtractor()
    extracted_doc = extractor.extract(docx_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    assert len(blocks) == 3
    assert blocks[0].source_text == "First paragraph before table."
    assert blocks[0].sequence_index == 0

    assert blocks[1].source_text == "Key | Value"
    assert blocks[1].metadata.get("is_table_row") is True
    assert blocks[1].sequence_index == 1

    assert blocks[2].source_text == "Second paragraph after table."
    assert blocks[2].sequence_index == 2

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]

    assert seg_blocks[0].type == BlockType.PARAGRAPH
    assert seg_blocks[1].type == BlockType.TABLE
    assert seg_blocks[2].type == BlockType.PARAGRAPH

    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented)
    assert report.is_valid
    assert report.total_blocks_checked == 3


# -----------------------------------------------------------------------------
# 10. Audit Refinement Tests: EPUB Direct Quote Text & Tables
# -----------------------------------------------------------------------------


def test_epub_blockquote_with_direct_text_and_child_paragraph(tmp_path: Path) -> None:
    """Verify direct text before/after child paragraph in blockquote is preserved in reading order."""
    epub_file = tmp_path / "bq_direct_text.epub"
    book = epub.EpubBook()
    book.set_identifier("epub-bq-direct-text-test")
    book.set_title("Direct Text Quote Book")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<h1>Chapter 1: Dialogue</h1>"
        "<blockquote>\n"
        "  Text before paragraph\n"
        "  <p>Nested paragraph</p>\n"
        "  Text after paragraph\n"
        "</blockquote>\n"
        "</body></html>"
    )
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    extracted_doc = extractor.extract(epub_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    # Verify all 4 blocks (heading + 3 quote fragments) in reading order
    assert len(blocks) == 4
    assert blocks[0].source_text == "Chapter 1: Dialogue"
    assert blocks[0].type == BlockType.HEADING

    assert blocks[1].source_text == "Text before paragraph"
    assert blocks[1].metadata.get("is_quote") is True
    assert blocks[1].metadata.get("quote_depth") == 1
    assert blocks[1].metadata.get("tag") == "blockquote"

    assert blocks[2].source_text == "Nested paragraph"
    assert blocks[2].metadata.get("is_quote") is True
    assert blocks[2].metadata.get("quote_depth") == 1
    assert blocks[2].metadata.get("tag") == "p"
    assert blocks[2].metadata.get("parent_tag") == "blockquote"

    assert blocks[3].source_text == "Text after paragraph"
    assert blocks[3].metadata.get("is_quote") is True
    assert blocks[3].metadata.get("quote_depth") == 1
    assert blocks[3].metadata.get("tag") == "blockquote"

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]

    assert seg_blocks[0].type == BlockType.HEADING
    assert seg_blocks[1].type == BlockType.BLOCKQUOTE
    assert seg_blocks[2].type == BlockType.BLOCKQUOTE
    assert seg_blocks[3].type == BlockType.BLOCKQUOTE


def test_epub_nested_blockquotes_with_direct_text_and_blocks(tmp_path: Path) -> None:
    """Verify nested blockquotes containing both direct text and child block elements."""
    epub_file = tmp_path / "nested_bq_mixed.epub"
    book = epub.EpubBook()
    book.set_identifier("epub-nested-bq-mixed")
    book.set_title("Nested BQ Mixed")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<blockquote>\n"
        "  Outer preamble\n"
        "  <blockquote>\n"
        "    Inner direct text\n"
        "    <p>Inner paragraph</p>\n"
        "    Inner after text\n"
        "  </blockquote>\n"
        "  Outer postamble\n"
        "</blockquote>\n"
        "</body></html>"
    )
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    extracted_doc = extractor.extract(epub_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    texts = [b.source_text for b in blocks]
    assert texts == [
        "Outer preamble",
        "Inner direct text",
        "Inner paragraph",
        "Inner after text",
        "Outer postamble",
    ]

    # Verify quote depths
    assert blocks[0].metadata.get("quote_depth") == 1
    assert blocks[1].metadata.get("quote_depth") == 2
    assert blocks[2].metadata.get("quote_depth") == 2
    assert blocks[3].metadata.get("quote_depth") == 2
    assert blocks[4].metadata.get("quote_depth") == 1

    for b in blocks:
        assert b.metadata.get("is_quote") is True

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]
    for b in seg_blocks:
        assert b.type == BlockType.BLOCKQUOTE


def test_epub_plain_text_table_with_empty_cells_between_paragraphs(tmp_path: Path) -> None:
    """Verify EPUB tables with plain text cells and empty cells between paragraphs."""
    epub_file = tmp_path / "table_between_paras.epub"
    book = epub.EpubBook()
    book.set_identifier("epub-table-test")
    book.set_title("Table Between Paras")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<p>Preamble before table.</p>"
        "<table>"
        "  <thead>"
        "    <tr><th>Header A</th><th>Header B</th><th>Header C</th></tr>"
        "  </thead>"
        "  <tbody>"
        "    <tr><td>Value A1</td><td></td><td>Value C1</td></tr>"
        "    <tr><td>Value A2</td><td>Value B2</td><td>Value C2</td></tr>"
        "  </tbody>"
        "</table>"
        "<p>Postamble after table.</p>"
        "</body></html>"
    )
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_file), book)

    extractor = EPUBExtractor()
    extracted_doc = extractor.extract(epub_file)
    blocks = [b for ch in extracted_doc.chapters for s in ch.sections for b in s.blocks]

    # 1 preamble + 3 table rows + 1 postamble = 5 blocks
    assert len(blocks) == 5

    # Paragraph before table
    assert blocks[0].source_text == "Preamble before table."
    assert blocks[0].sequence_index == 0

    # Table Row 0 (Header)
    assert blocks[1].source_text == "Header A | Header B | Header C"
    assert blocks[1].metadata.get("is_table_row") is True
    assert blocks[1].metadata.get("cells_count") == 3
    assert blocks[1].metadata.get("row_index") == 0
    assert blocks[1].metadata.get("total_rows") == 3
    assert blocks[1].sequence_index == 1
    assert blocks[1].metadata.get("cells") == ["Header A", "Header B", "Header C"]
    assert blocks[1].metadata.get("is_header_row") is True
    assert isinstance(blocks[1].metadata.get("table_id"), str)

    # Table Row 1 (Empty middle cell preserved)
    assert blocks[2].source_text == "Value A1 |  | Value C1"
    assert blocks[2].metadata.get("is_table_row") is True
    assert blocks[2].metadata.get("cells_count") == 3
    assert blocks[2].metadata.get("row_index") == 1
    assert blocks[2].sequence_index == 2
    assert blocks[2].metadata.get("cells") == ["Value A1", "", "Value C1"]
    assert blocks[2].metadata.get("is_header_row") is False
    assert blocks[2].metadata.get("table_id") == blocks[1].metadata.get("table_id")

    # Table Row 2
    assert blocks[3].source_text == "Value A2 | Value B2 | Value C2"
    assert blocks[3].metadata.get("is_table_row") is True
    assert blocks[3].metadata.get("cells_count") == 3
    assert blocks[3].metadata.get("row_index") == 2
    assert blocks[3].sequence_index == 3
    assert blocks[3].metadata.get("cells") == ["Value A2", "Value B2", "Value C2"]
    assert blocks[3].metadata.get("is_header_row") is False
    assert blocks[3].metadata.get("table_id") == blocks[1].metadata.get("table_id")

    # Paragraph after table
    assert blocks[4].source_text == "Postamble after table."
    assert blocks[4].sequence_index == 4

    # Segment via pipeline
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented = pipeline.segment(extracted_doc)
    seg_blocks = [b for ch in segmented.chapters for s in ch.sections for b in s.blocks]

    assert seg_blocks[0].type == BlockType.PARAGRAPH
    assert seg_blocks[1].type == BlockType.TABLE
    assert seg_blocks[2].type == BlockType.TABLE
    assert seg_blocks[3].type == BlockType.TABLE
    assert seg_blocks[4].type == BlockType.PARAGRAPH

    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented)
    assert report.is_valid
    assert report.total_blocks_checked == 5


def _build_test_epub(file_path: Path, html_content: str, title: str = "Test Book") -> None:
    """Helper to build a valid EPUB with NCX and NAV for testing."""
    book = epub.EpubBook()
    book.set_identifier(f"epub-{file_path.stem}")
    book.set_title(title)
    book.set_language("en")
    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = html_content
    book.add_item(c1)
    book.toc = (c1,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]
    epub.write_epub(str(file_path), book)


def test_table_one_table_multiple_rows_shared_table_id(tmp_path: Path) -> None:
    """Verify one table with multiple rows shares a single stable table_id in DOCX and EPUB."""
    # 1. DOCX Test
    docx_file = tmp_path / "shared_table_id.docx"
    doc_docx = docx.Document()
    t_docx = doc_docx.add_table(rows=3, cols=2)
    t_docx.rows[0].cells[0].text = "H1"
    t_docx.rows[0].cells[1].text = "H2"
    t_docx.rows[1].cells[0].text = "R1C1"
    t_docx.rows[1].cells[1].text = "R1C2"
    t_docx.rows[2].cells[0].text = "R2C1"
    t_docx.rows[2].cells[1].text = "R2C2"
    doc_docx.save(str(docx_file))

    docx_ext = DOCXExtractor()
    doc_res = docx_ext.extract(docx_file)
    docx_blocks = [b for ch in doc_res.chapters for s in ch.sections for b in s.blocks]
    assert len(docx_blocks) == 3

    tbl_id = docx_blocks[0].metadata.get("table_id")
    assert isinstance(tbl_id, str)
    assert UUID(tbl_id)  # Validates UUID format
    for idx, b in enumerate(docx_blocks):
        assert b.metadata.get("table_id") == tbl_id
        assert b.metadata.get("row_index") == idx
        assert b.metadata.get("total_rows") == 3
        assert b.metadata.get("cells_count") == 2
        assert b.metadata.get("tag") == "table"
        assert b.metadata.get("style_name") == "Table"
        assert b.metadata.get("is_table_row") is True

    # 2. EPUB Test
    epub_file = tmp_path / "shared_table_id.epub"
    epub_html = (
        "<html><body>"
        "<table>"
        "  <tr><td>E_H1</td><td>E_H2</td></tr>"
        "  <tr><td>E_R1C1</td><td>E_R1C2</td></tr>"
        "  <tr><td>E_R2C1</td><td>E_R2C2</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Shared Table ID")

    epub_ext = EPUBExtractor()
    epub_doc = epub_ext.extract(epub_file)
    epub_blocks = [b for ch in epub_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(epub_blocks) == 3

    e_tbl_id = epub_blocks[0].metadata.get("table_id")
    assert isinstance(e_tbl_id, str)
    assert UUID(e_tbl_id)
    for idx, b in enumerate(epub_blocks):
        assert b.metadata.get("table_id") == e_tbl_id
        assert b.metadata.get("row_index") == idx
        assert b.metadata.get("total_rows") == 3
        assert b.metadata.get("cells_count") == 2


def test_table_two_consecutive_tables_different_table_ids(tmp_path: Path) -> None:
    """Verify two consecutive tables without intervening paragraphs have distinct table_ids."""
    # 1. DOCX Test: Two consecutive tables
    docx_file = tmp_path / "consecutive_tables.docx"
    doc_docx = docx.Document()
    t1 = doc_docx.add_table(rows=2, cols=2)
    t1.rows[0].cells[0].text = "T1_R0_C0"
    t1.rows[0].cells[1].text = "T1_R0_C1"
    t1.rows[1].cells[0].text = "T1_R1_C0"
    t1.rows[1].cells[1].text = "T1_R1_C1"

    t2 = doc_docx.add_table(rows=2, cols=2)
    t2.rows[0].cells[0].text = "T2_R0_C0"
    t2.rows[0].cells[1].text = "T2_R0_C1"
    t2.rows[1].cells[0].text = "T2_R1_C0"
    t2.rows[1].cells[1].text = "T2_R1_C1"
    doc_docx.save(str(docx_file))

    docx_ext = DOCXExtractor()
    docx_doc = docx_ext.extract(docx_file)
    d_blocks = [b for ch in docx_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(d_blocks) == 4

    t1_id = d_blocks[0].metadata.get("table_id")
    t2_id = d_blocks[2].metadata.get("table_id")
    assert isinstance(t1_id, str)
    assert isinstance(t2_id, str)
    assert t1_id != t2_id

    # Table 1 rows
    assert d_blocks[0].metadata.get("table_id") == t1_id
    assert d_blocks[0].metadata.get("row_index") == 0
    assert d_blocks[0].metadata.get("total_rows") == 2
    assert d_blocks[1].metadata.get("table_id") == t1_id
    assert d_blocks[1].metadata.get("row_index") == 1
    assert d_blocks[1].metadata.get("total_rows") == 2

    # Table 2 rows
    assert d_blocks[2].metadata.get("table_id") == t2_id
    assert d_blocks[2].metadata.get("row_index") == 0
    assert d_blocks[2].metadata.get("total_rows") == 2
    assert d_blocks[3].metadata.get("table_id") == t2_id
    assert d_blocks[3].metadata.get("row_index") == 1
    assert d_blocks[3].metadata.get("total_rows") == 2

    # 2. EPUB Test: Two consecutive tables
    epub_file = tmp_path / "consecutive_tables.epub"
    epub_html = (
        "<html><body>"
        "<table>"
        "  <tr><td>T1_A</td><td>T1_B</td></tr>"
        "  <tr><td>T1_C</td><td>T1_D</td></tr>"
        "</table>"
        "<table>"
        "  <tr><td>T2_A</td><td>T2_B</td></tr>"
        "  <tr><td>T2_C</td><td>T2_D</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Consecutive Tables")

    epub_ext = EPUBExtractor()
    epub_doc = epub_ext.extract(epub_file)
    e_blocks = [b for ch in epub_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(e_blocks) == 4

    e_t1_id = e_blocks[0].metadata.get("table_id")
    e_t2_id = e_blocks[2].metadata.get("table_id")
    assert isinstance(e_t1_id, str)
    assert isinstance(e_t2_id, str)
    assert e_t1_id != e_t2_id

    assert e_blocks[0].metadata.get("table_id") == e_t1_id
    assert e_blocks[1].metadata.get("table_id") == e_t1_id
    assert e_blocks[2].metadata.get("table_id") == e_t2_id
    assert e_blocks[3].metadata.get("table_id") == e_t2_id


def test_table_cell_with_pipe_and_double_pipe_preserved(tmp_path: Path) -> None:
    """Verify cells containing '|' or '||' (Sanskrit danda) remain intact in metadata['cells']."""
    danda_verse = "om tat sat | iti nirdeso || 17.23 ||"
    danda_commentary = "Threefold designation | of Brahman"

    # 1. DOCX
    docx_file = tmp_path / "pipe_cells.docx"
    doc_docx = docx.Document()
    t_docx = doc_docx.add_table(rows=1, cols=2)
    t_docx.rows[0].cells[0].text = danda_verse
    t_docx.rows[0].cells[1].text = danda_commentary
    doc_docx.save(str(docx_file))

    docx_ext = DOCXExtractor()
    doc_res = docx_ext.extract(docx_file)
    d_blocks = [b for ch in doc_res.chapters for s in ch.sections for b in s.blocks]
    assert len(d_blocks) == 1
    d_meta = d_blocks[0].metadata
    assert d_meta.get("cells_count") == 2
    assert d_meta.get("cells") == [danda_verse, danda_commentary]
    # source_text joins by " | ", but metadata['cells'] preserves exact individual cell content
    assert d_blocks[0].source_text == f"{danda_verse} | {danda_commentary}"

    # 2. EPUB
    epub_file = tmp_path / "pipe_cells.epub"
    epub_html = (
        "<html><body>"
        "<table>"
        f"  <tr><td>{danda_verse}</td><td>{danda_commentary}</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Pipes Test")

    epub_ext = EPUBExtractor()
    epub_doc = epub_ext.extract(epub_file)
    e_blocks = [b for ch in epub_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(e_blocks) == 1
    e_meta = e_blocks[0].metadata
    assert e_meta.get("cells_count") == 2
    assert e_meta.get("cells") == [danda_verse, danda_commentary]


def test_table_with_empty_cells_and_completely_empty_row(tmp_path: Path) -> None:
    """Verify preservation of empty cells and completely empty rows without discarding."""
    # 1. DOCX Test
    docx_file = tmp_path / "empty_rows.docx"
    doc_docx = docx.Document()
    t_docx = doc_docx.add_table(rows=3, cols=3)
    # Row 0: Full header
    t_docx.rows[0].cells[0].text = "Col A"
    t_docx.rows[0].cells[1].text = "Col B"
    t_docx.rows[0].cells[2].text = "Col C"
    # Row 1: Completely empty row (all cells "")
    t_docx.rows[1].cells[0].text = ""
    t_docx.rows[1].cells[1].text = ""
    t_docx.rows[1].cells[2].text = ""
    # Row 2: Empty middle cell
    t_docx.rows[2].cells[0].text = "Val 1"
    t_docx.rows[2].cells[1].text = ""
    t_docx.rows[2].cells[2].text = "Val 3"
    doc_docx.save(str(docx_file))

    docx_ext = DOCXExtractor()
    docx_doc = docx_ext.extract(docx_file)
    d_blocks = [b for ch in docx_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(d_blocks) == 3

    assert d_blocks[0].metadata.get("cells") == ["Col A", "Col B", "Col C"]
    assert d_blocks[0].metadata.get("row_index") == 0
    assert d_blocks[0].metadata.get("total_rows") == 3

    # Row 1: completely empty row preserved
    assert d_blocks[1].metadata.get("cells") == ["", "", ""]
    assert d_blocks[1].metadata.get("cells_count") == 3
    assert d_blocks[1].metadata.get("row_index") == 1
    assert d_blocks[1].metadata.get("total_rows") == 3

    # Row 2: middle empty cell preserved
    assert d_blocks[2].metadata.get("cells") == ["Val 1", "", "Val 3"]
    assert d_blocks[2].metadata.get("cells_count") == 3
    assert d_blocks[2].metadata.get("row_index") == 2
    assert d_blocks[2].metadata.get("total_rows") == 3

    # 2. EPUB Test
    epub_file = tmp_path / "empty_rows.epub"
    epub_html = (
        "<html><body>"
        "<table>"
        "  <tr><td>Col A</td><td>Col B</td><td>Col C</td></tr>"
        "  <tr><td></td><td></td><td></td></tr>"
        "  <tr><td>Val 1</td><td></td><td>Val 3</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Empty Rows Test")

    epub_ext = EPUBExtractor()
    epub_doc = epub_ext.extract(epub_file)
    e_blocks = [b for ch in epub_doc.chapters for s in ch.sections for b in s.blocks]
    assert len(e_blocks) == 3

    assert e_blocks[0].metadata.get("cells") == ["Col A", "Col B", "Col C"]
    assert e_blocks[0].metadata.get("row_index") == 0

    assert e_blocks[1].metadata.get("cells") == ["", "", ""]
    assert e_blocks[1].metadata.get("cells_count") == 3
    assert e_blocks[1].metadata.get("row_index") == 1
    assert e_blocks[1].metadata.get("total_rows") == 3

    assert e_blocks[2].metadata.get("cells") == ["Val 1", "", "Val 3"]
    assert e_blocks[2].metadata.get("cells_count") == 3
    assert e_blocks[2].metadata.get("row_index") == 2
    assert e_blocks[2].metadata.get("total_rows") == 3


def test_epub_th_and_thead_header_detection(tmp_path: Path) -> None:
    """Verify EPUB distinguishes header rows via <th> or <thead> without guessing on ordinary rows."""
    epub_file = tmp_path / "header_detection.epub"
    epub_html = (
        "<html><body>"
        # Table 1: thead with th
        "<table id='tbl-1'>"
        "  <thead><tr><th>Head 1</th><th>Head 2</th></tr></thead>"
        "  <tbody><tr><td>Body 1</td><td>Body 2</td></tr></tbody>"
        "</table>"
        # Table 2: th without thead
        "<table id='tbl-2'>"
        "  <tr><th>Col Head A</th><th>Col Head B</th></tr>"
        "  <tr><td>Data A</td><td>Data B</td></tr>"
        "</table>"
        # Table 3: plain td only (no explicit header markup)
        "<table id='tbl-3'>"
        "  <tr><td>Plain 1</td><td>Plain 2</td></tr>"
        "  <tr><td>Plain 3</td><td>Plain 4</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Header Detection Test")

    extractor = EPUBExtractor()
    doc = extractor.extract(epub_file)
    blocks = [b for ch in doc.chapters for s in ch.sections for b in s.blocks]
    assert len(blocks) == 6

    # Table 1
    assert blocks[0].metadata.get("is_header_row") is True  # inside thead, has th
    assert blocks[1].metadata.get("is_header_row") is False  # inside tbody, has td

    # Table 2
    assert blocks[2].metadata.get("is_header_row") is True  # has th
    assert blocks[3].metadata.get("is_header_row") is False  # has td

    # Table 3 (no thead, no th -> should NOT guess that row 0 is header)
    assert blocks[4].metadata.get("is_header_row") is False
    assert blocks[5].metadata.get("is_header_row") is False


def test_docx_tblheader_header_detection(tmp_path: Path) -> None:
    """Verify DOCX detects w:tblHeader property and does not guess headers when absent."""
    docx_file = tmp_path / "docx_headers.docx"
    doc_docx = docx.Document()

    # Table 1: Header set via w:tblHeader on row 0
    t1 = doc_docx.add_table(rows=2, cols=2)
    t1.rows[0].cells[0].text = "Header 1"
    t1.rows[0].cells[1].text = "Header 2"
    t1.rows[1].cells[0].text = "Data 1"
    t1.rows[1].cells[1].text = "Data 2"

    tr_pr = t1.rows[0]._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tr_pr.append(tbl_header)

    # Table 2: Ordinary table without w:tblHeader
    t2 = doc_docx.add_table(rows=2, cols=2)
    t2.rows[0].cells[0].text = "Normal 1"
    t2.rows[0].cells[1].text = "Normal 2"
    t2.rows[1].cells[0].text = "Normal 3"
    t2.rows[1].cells[1].text = "Normal 4"

    doc_docx.save(str(docx_file))

    extractor = DOCXExtractor()
    doc = extractor.extract(docx_file)
    blocks = [b for ch in doc.chapters for s in ch.sections for b in s.blocks]
    assert len(blocks) == 4

    # Table 1: row 0 has w:tblHeader, row 1 does not
    assert blocks[0].metadata.get("is_header_row") is True
    assert blocks[1].metadata.get("is_header_row") is False

    # Table 2: neither row has w:tblHeader -> should NOT guess
    assert blocks[2].metadata.get("is_header_row") is False
    assert blocks[3].metadata.get("is_header_row") is False


def test_table_consistent_metadata_schema_between_docx_and_epub(tmp_path: Path) -> None:
    """Verify DOCX and EPUB table blocks follow the exact same unified metadata schema."""
    # 1. Create DOCX
    docx_file = tmp_path / "schema_docx.docx"
    doc_docx = docx.Document()
    t = doc_docx.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "H1"
    t.rows[0].cells[1].text = "H2"
    t.rows[1].cells[0].text = "D1"
    t.rows[1].cells[1].text = "D2"
    doc_docx.save(str(docx_file))

    # 2. Create EPUB
    epub_file = tmp_path / "schema_epub.epub"
    epub_html = (
        "<html><body>"
        "<table>"
        "  <tr><th>H1</th><th>H2</th></tr>"
        "  <tr><td>D1</td><td>D2</td></tr>"
        "</table>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Schema Test")

    # Extract both
    docx_blocks = [
        b
        for ch in DOCXExtractor().extract(docx_file).chapters
        for s in ch.sections
        for b in s.blocks
    ]
    epub_blocks = [
        b
        for ch in EPUBExtractor().extract(epub_file).chapters
        for s in ch.sections
        for b in s.blocks
    ]

    required_keys = {
        "tag",
        "style_name",
        "is_table_row",
        "table_id",
        "row_index",
        "total_rows",
        "cells_count",
        "cells",
        "is_header_row",
    }

    for b in docx_blocks + epub_blocks:
        meta = b.metadata
        assert required_keys.issubset(set(meta.keys()))
        assert meta["tag"] == "table"
        assert meta["style_name"] == "Table"
        assert meta["is_table_row"] is True
        assert isinstance(meta["table_id"], str) and len(meta["table_id"]) > 0
        assert UUID(meta["table_id"])  # Valid UUID
        assert isinstance(meta["row_index"], int) and meta["row_index"] >= 0
        assert isinstance(meta["total_rows"], int) and meta["total_rows"] > 0
        assert isinstance(meta["cells_count"], int) and meta["cells_count"] == len(meta["cells"])
        assert isinstance(meta["cells"], list) and all(isinstance(c, str) for c in meta["cells"])
        assert isinstance(meta["is_header_row"], bool)


def test_table_paragraph_reading_order_preservation(tmp_path: Path) -> None:
    """Verify document reading order and sequence_index are preserved across interleaved tables."""
    epub_file = tmp_path / "reading_order.epub"
    epub_html = (
        "<html><body>"
        "<p>Preamble paragraph.</p>"
        "<table>"
        "  <tr><td>T1_R0_C0</td><td>T1_R0_C1</td></tr>"
        "  <tr><td>T1_R1_C0</td><td>T1_R1_C1</td></tr>"
        "</table>"
        "<p>Intermediary paragraph.</p>"
        "<table>"
        "  <tr><td>T2_R0_C0</td><td>T2_R0_C1</td></tr>"
        "  <tr><td>T2_R1_C0</td><td>T2_R1_C1</td></tr>"
        "</table>"
        "<p>Postamble paragraph.</p>"
        "</body></html>"
    )
    _build_test_epub(epub_file, epub_html, "Reading Order")

    extractor = EPUBExtractor()
    raw_doc = extractor.extract(epub_file)
    pipeline = SegmenterPipeline(clock=fixed_clock)
    segmented_doc = pipeline.segment(raw_doc)
    blocks = [b for ch in segmented_doc.chapters for s in ch.sections for b in s.blocks]

    # Expected: 7 blocks
    assert len(blocks) == 7

    assert blocks[0].type == BlockType.PARAGRAPH
    assert blocks[0].source_text == "Preamble paragraph."
    assert blocks[0].sequence_index == 0

    assert blocks[1].type == BlockType.TABLE
    assert blocks[1].sequence_index == 1

    assert blocks[2].type == BlockType.TABLE
    assert blocks[2].sequence_index == 2

    assert blocks[3].type == BlockType.PARAGRAPH
    assert blocks[3].source_text == "Intermediary paragraph."
    assert blocks[3].sequence_index == 3

    assert blocks[4].type == BlockType.TABLE
    assert blocks[4].sequence_index == 4

    assert blocks[5].type == BlockType.TABLE
    assert blocks[5].sequence_index == 5

    assert blocks[6].type == BlockType.PARAGRAPH
    assert blocks[6].source_text == "Postamble paragraph."
    assert blocks[6].sequence_index == 6

    # Verify tables have different IDs
    assert blocks[1].metadata.get("table_id") == blocks[2].metadata.get("table_id")
    assert blocks[4].metadata.get("table_id") == blocks[5].metadata.get("table_id")
    assert blocks[1].metadata.get("table_id") != blocks[4].metadata.get("table_id")

    # Invariants pass
    validator = DocumentIntegrityValidator(raise_on_error=True)
    report = validator.validate(segmented_doc)
    assert report.is_valid
    assert report.total_blocks_checked == 7
