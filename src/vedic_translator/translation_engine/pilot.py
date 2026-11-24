"""Minimal translation pilot for MVP B translating pages 215-216 using Gemini."""

import time
from pathlib import Path
from typing import Any
from uuid import UUID

import dotenv
from loguru import logger

from vedic_translator.core.models import Chapter, Document, DocumentStatus, Section
from vedic_translator.document_processor.extractors.pdf import PDFExtractor
from vedic_translator.document_processor.extractors.text_cleaner import (
    sanitize_translation,
    sanitize_transliteration,
    sanitize_verse_text,
)
from vedic_translator.document_processor.segmenter.pipeline import SegmenterPipeline
from vedic_translator.document_processor.segmenter.relationships.profiles import (
    RAMCHARITA_MANAS_PROFILE,
)
from vedic_translator.translation_engine.providers.base import (
    ContextItem,
    ProviderConfig,
    TranslationPayload,
)
from vedic_translator.translation_engine.providers.gemini import GeminiTranslationProvider
from vedic_translator.translation_engine.storage.models import (
    JobStatus,
    TranslationJobRecord,
    TranslationUnitRecord,
    TranslationVersionRecord,
    UnitStatus,
    VersionStage,
    compute_source_content_hash,
)
from vedic_translator.translation_engine.storage.repository import TranslationStorage

PILOT_JOB_ID = "pilot-bala-kanda-p215-216"
DEFAULT_PDF_PATH = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
DEFAULT_DB_PATH = Path("data/temp/pilot_workspace.db")


def extract_pilot_units(
    pdf_path: Path = DEFAULT_PDF_PATH,
) -> list[dict[str, Any]]:
    """Extract and semantically segment the 5 target pilot VerseUnits from pages 215-216.

    Returns a list of structured dictionaries with original Awadhi, IAST, and English reference.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF source not found at: {pdf_path}")

    logger.info(f"Extracting document from {pdf_path.name}...")
    extractor = PDFExtractor()
    doc = extractor.extract(pdf_path)

    target_pages = {215, 216}
    sample_blocks = [
        b
        for ch in doc.chapters
        for s in ch.sections
        for b in s.blocks
        if b.metadata.get("page") in target_pages
    ]
    logger.info(f"Found {len(sample_blocks)} blocks on pages 215-216.")

    sub_doc = Document(
        metadata=doc.metadata,
        chapters=[
            Chapter(
                chapter_index=1,
                title="Bala Kanda",
                sections=[Section(section_index=1, blocks=sample_blocks)],
            )
        ],
        status=DocumentStatus.INGESTED,
    )

    logger.info("Executing relationship resolution pipeline...")
    pipeline = SegmenterPipeline(relationship_profile=RAMCHARITA_MANAS_PROFILE)
    enriched_doc = pipeline.segment(sub_doc)
    sec = enriched_doc.chapters[0].sections[0]

    block_map = {b.id: b for b in sample_blocks}
    canonical_labels = ["1.188", "1.189.1", "1.189.2", "1.189.3", "1.189.4"]

    extracted_units: list[dict[str, Any]] = []
    for i in range(min(5, len(sec.verse_units))):
        vu = sec.verse_units[i]
        orig = " ".join(
            block_map[bid].source_text for bid in vu.original_script_block_ids if bid in block_map
        ).strip()
        translit = " ".join(
            block_map[bid].source_text for bid in vu.transliteration_block_ids if bid in block_map
        ).strip()
        english = " ".join(
            block_map[bid].source_text for bid in vu.translation_block_ids if bid in block_map
        ).strip()

        # Sanitize metrical marker prefixes, trailing page numbers, and typographic spacing
        clean_orig = sanitize_verse_text(orig)
        clean_translit = sanitize_transliteration(translit)
        clean_english = sanitize_translation(english)

        extracted_units.append(
            {
                "unit_id": vu.id,
                "canonical_id": canonical_labels[i],
                "unit_type": vu.unit_type.value,
                "original_text": clean_orig,
                "transliteration": clean_translit or None,
                "english_reference": clean_english or None,
                "chapter_index": 1,
                "section_index": 1,
                "sequence_order": i + 1,
            }
        )

    logger.info(f"Successfully prepared {len(extracted_units)} pilot units.")
    return extracted_units


def execute_pilot(
    pdf_path: Path = DEFAULT_PDF_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    provider: GeminiTranslationProvider | None = None,
    storage: TranslationStorage | None = None,
    delay_between_requests: float = 1.0,
) -> dict[str, Any]:
    """Execute the 5-unit translation pilot on pages 215-216 and persist to SQLite.

    Args:
        pdf_path: Path to the Ramcharit Manas PDF.
        db_path: Path to the destination SQLite workspace database.
        provider: Optional injected translation provider (for testing/mocking).
        storage: Optional injected storage repository.
        delay_between_requests: Politeness delay in seconds between Gemini API calls.

    Returns:
        Structured dictionary containing translation results, token metrics, and storage confirmation.
    """
    dotenv.load_dotenv()

    # Initialize storage repository
    if storage is None:
        storage = TranslationStorage(db_path)

    # Initialize Gemini provider
    if provider is None:
        provider = GeminiTranslationProvider()

    # Ensure pilot translation job exists in database
    job = storage.get_job(PILOT_JOB_ID)
    if not job:
        job = TranslationJobRecord(
            job_id=PILOT_JOB_ID,
            document_id="ramcharita-manas-gita-press",
            book_title="Sri Ramcharit Manas (Gita Press Bala Kanda Pilot)",
            source_language="awa",
            target_language="ru",
            provider_name=provider.provider_name,
            model_name="gemini-3.5-flash-lite",
            status=JobStatus.RUNNING,
            total_units=5,
            config={"temperature": 0.2, "pages": [215, 216]},
        )
        storage.create_job(job)
    else:
        if job.status in (JobStatus.FAILED, JobStatus.PAUSED):
            storage.update_job_status(job.job_id, JobStatus.RUNNING)

    # Extract 5 pilot units
    units_data = extract_pilot_units(pdf_path)

    results: list[dict[str, Any]] = []
    preceding_context: list[ContextItem] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for item in units_data:
        unit_id_str = str(item["unit_id"])
        canonical_id = item["canonical_id"]
        original_text = item["original_text"]
        transliteration = item["transliteration"]
        english_ref = item["english_reference"]
        unit_type = item["unit_type"]

        logger.info(
            f"Processing pilot unit {canonical_id} ({unit_type}) [{item['sequence_order']}/5]..."
        )

        content_hash = compute_source_content_hash(
            original_text=original_text,
            transliteration=transliteration,
            reference_english=english_ref,
        )

        # Idempotently upsert unit record into SQLite
        unit_record = TranslationUnitRecord(
            unit_id=unit_id_str,
            job_id=job.job_id,
            canonical_id=canonical_id,
            unit_type=unit_type,
            sequence_order=item["sequence_order"],
            chapter_index=item["chapter_index"],
            section_index=item["section_index"],
            content_hash=content_hash,
            source_original_text=original_text,
            source_transliteration_text=transliteration,
            source_reference_english=english_ref,
            status=UnitStatus.PENDING,
        )
        storage.upsert_unit(unit_record)

        # Transition to PROCESSING
        storage.update_unit_status(unit_id_str, UnitStatus.PROCESSING, increment_attempts=True)

        # Build provider-neutral TranslationPayload
        payload = TranslationPayload(
            unit_id=UUID(unit_id_str),
            canonical_id=canonical_id,
            unit_type=unit_type,
            original_text=original_text,
            transliteration=transliteration,
            reference_translation=english_ref,
            canto_name="Bala Kanda",
            narrative_episode="Putrakameshti Yajna & Advent of Sri Rama (Pages 215-216)",
            preceding_context=preceding_context,
        )

        # Execute translation call
        t0 = time.perf_counter()
        response = provider.translate(payload, config=ProviderConfig(temperature=0.2))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Track tokens
        if response.token_usage:
            total_prompt_tokens += response.token_usage.input_tokens
            total_completion_tokens += response.token_usage.output_tokens
            total_tokens += response.token_usage.total_tokens

        # Create persistent translation version in SQLite (transitions PROCESSING -> TRANSLATED)
        version = TranslationVersionRecord(
            unit_id=unit_id_str,
            source_stage=VersionStage.AI_DRAFT,
            translated_verse_russian=response.russian_verse,
            translated_commentary_russian=response.russian_commentary,
            translator_notes=response.translator_notes,
            confidence_assessment=response.confidence_assessment.model_dump(),
            token_usage=(response.token_usage.model_dump() if response.token_usage else None),
            model_name=response.model_name,
        )
        persisted_version = storage.create_version(
            unit_id_str, version, new_unit_status=UnitStatus.TRANSLATED
        )

        current_unit_status = UnitStatus.TRANSLATED
        # Flag for human review if model reported low confidence
        if (
            response.confidence_assessment.theological_clarity == "LOW"
            or response.confidence_assessment.linguistic_certainty == "LOW"
        ):
            logger.warning(
                f"Unit {canonical_id} flagged for review due to low confidence: {response.confidence_assessment.ambiguity_notes}"
            )
            storage.update_unit_status(
                unit_id_str,
                UnitStatus.QC_FAILED,
                error_message=response.confidence_assessment.ambiguity_notes
                or "Low model confidence",
            )
            storage.update_unit_status(unit_id_str, UnitStatus.NEEDS_REVIEW)
            current_unit_status = UnitStatus.NEEDS_REVIEW

        # Increment job progress
        storage.update_job_progress(job.job_id, completed_increment=1)

        # Maintain narrative continuity sliding window
        preceding_context.append(
            ContextItem(
                canonical_id=canonical_id,
                russian_verse=response.russian_verse,
            )
        )
        if len(preceding_context) > 2:
            preceding_context.pop(0)

        results.append(
            {
                "unit_id": unit_id_str,
                "canonical_id": canonical_id,
                "unit_type": unit_type,
                "original_text": original_text,
                "transliteration": transliteration,
                "english_reference": english_ref,
                "russian_verse": response.russian_verse,
                "russian_commentary": response.russian_commentary,
                "translator_notes": response.translator_notes,
                "confidence": response.confidence_assessment.model_dump(),
                "model_name": response.model_name,
                "token_usage": (response.token_usage.model_dump() if response.token_usage else {}),
                "latency_ms": latency_ms,
                "version_number": persisted_version.version_number,
                "status": current_unit_status.value,
            }
        )

        logger.info(
            f"Completed unit {canonical_id} in {latency_ms}ms (tokens: {response.token_usage.total_tokens if response.token_usage else 'N/A'})."
        )

        if delay_between_requests > 0:
            time.sleep(delay_between_requests)

    # Finalize job status
    stats = storage.get_job_statistics(job.job_id)
    final_job_status = (
        JobStatus.COMPLETED if stats.get("NEEDS_REVIEW", 0) == 0 else JobStatus.PAUSED
    )
    storage.update_job_status(job.job_id, final_job_status)

    return {
        "job_id": job.job_id,
        "job_status": final_job_status.value,
        "total_units_translated": len(results),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "db_path": str(db_path),
        "results": results,
    }


def execute_second_pilot(
    db_path: Path = DEFAULT_DB_PATH,
    provider: GeminiTranslationProvider | None = None,
    storage: TranslationStorage | None = None,
    delay_between_requests: float = 1.0,
) -> dict[str, Any]:
    """Execute the second translation pilot for the 5 units using the revised system prompt.

    Loads the exact 5 source units from the database (preserving version 1 unchanged)
    and saves the new translations as version 2.

    Args:
        db_path: Path to the SQLite database.
        provider: Optional injected translation provider (for testing/mocking).
        storage: Optional injected storage repository.
        delay_between_requests: Politeness delay in seconds between Gemini API calls.

    Returns:
        Structured dictionary containing version 1 and version 2 records, metrics,
        and preservation confirmations.
    """
    dotenv.load_dotenv()

    if storage is None:
        storage = TranslationStorage(db_path)

    if provider is None:
        provider = GeminiTranslationProvider()

    # Retrieve existing units that have version 1, ordered by sequence_order
    sql = """
    SELECT u.* FROM translation_units u
    JOIN translation_versions v ON u.unit_id = v.unit_id
    WHERE v.version_number = 1
    ORDER BY u.sequence_order ASC;
    """
    with storage.get_connection() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        raise ValueError(
            f"No existing units with version 1 found in database '{db_path}'. "
            "Please run pilot 1 first."
        )

    # Deduplicate in case of multiple unit records, preserving distinct units
    seen_units: set[str] = set()
    pilot_units: list[TranslationUnitRecord] = []
    for r in rows:
        uid = r["unit_id"]
        if uid not in seen_units:
            seen_units.add(uid)
            pilot_units.append(storage._row_to_unit(r))

    pilot_units = pilot_units[:5]

    results: list[dict[str, Any]] = []
    preceding_context: list[ContextItem] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for u in pilot_units:
        canonical_id = u.canonical_id
        unit_type = u.unit_type
        logger.info(
            f"[Pilot 2] Translating unit {canonical_id} ({unit_type}) [{u.sequence_order}/5]..."
        )

        # Get existing version 1 for audit and comparison
        existing_versions = storage.get_versions_for_unit(u.unit_id)
        v1 = existing_versions[0]

        # Construct TranslationPayload with exact source data
        payload = TranslationPayload(
            unit_id=UUID(u.unit_id),
            canonical_id=canonical_id,
            unit_type=unit_type,
            original_text=u.source_original_text,
            transliteration=u.source_transliteration_text,
            reference_translation=u.source_reference_english,
            commentary=u.source_commentary,  # None
            canto_name="Bala Kanda",
            narrative_episode="Putrakameshti Yajna & Advent of Sri Rama (Pages 215-216)",
            preceding_context=preceding_context,
        )

        # Execute translation call using revised system prompt
        t0 = time.perf_counter()
        response = provider.translate(payload, config=ProviderConfig(temperature=0.2))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        if response.token_usage:
            total_prompt_tokens += response.token_usage.input_tokens
            total_completion_tokens += response.token_usage.output_tokens
            total_tokens += response.token_usage.total_tokens

        # Persist new translation as Version 2
        new_version_record = TranslationVersionRecord(
            unit_id=u.unit_id,
            source_stage=VersionStage.AI_DRAFT,
            translated_verse_russian=response.russian_verse,
            translated_commentary_russian=response.russian_commentary,
            translator_notes=response.translator_notes,
            confidence_assessment=response.confidence_assessment.model_dump(),
            token_usage=(response.token_usage.model_dump() if response.token_usage else None),
            model_name=response.model_name,
        )
        persisted_v2 = storage.create_version(
            u.unit_id, new_version_record, new_unit_status=UnitStatus.TRANSLATED
        )

        # Confirm version numbering
        if persisted_v2.version_number != 2:
            raise ValueError(
                f"Expected version_number 2 for unit {canonical_id}, but got {persisted_v2.version_number}"
            )

        # Verify that version 1 is unchanged
        all_versions_after = storage.get_versions_for_unit(u.unit_id)
        v1_after = all_versions_after[0]
        v1_unchanged = (
            v1_after.version_id == v1.version_id
            and v1_after.version_number == 1
            and v1_after.translated_verse_russian == v1.translated_verse_russian
        )

        # Maintain narrative continuity sliding window with v2 text
        preceding_context.append(
            ContextItem(
                canonical_id=canonical_id,
                russian_verse=response.russian_verse,
            )
        )
        if len(preceding_context) > 2:
            preceding_context.pop(0)

        results.append(
            {
                "canonical_id": canonical_id,
                "unit_id": u.unit_id,
                "unit_type": unit_type,
                "original_text": u.source_original_text,
                "transliteration": u.source_transliteration_text,
                "english_reference": u.source_reference_english,
                "version_1": {
                    "version_id": v1.version_id,
                    "version_number": v1.version_number,
                    "russian_verse": v1.translated_verse_russian,
                    "russian_commentary": v1.translated_commentary_russian,
                    "translator_notes": v1.translator_notes,
                    "confidence": v1.confidence_assessment,
                    "created_at": v1.created_at.isoformat(),
                },
                "version_2": {
                    "version_id": persisted_v2.version_id,
                    "version_number": persisted_v2.version_number,
                    "russian_verse": response.russian_verse,
                    "russian_commentary": response.russian_commentary,
                    "translator_notes": response.translator_notes,
                    "confidence": response.confidence_assessment.model_dump(),
                    "model_name": response.model_name,
                    "token_usage": (
                        response.token_usage.model_dump() if response.token_usage else {}
                    ),
                    "latency_ms": latency_ms,
                    "created_at": persisted_v2.created_at.isoformat(),
                },
                "v1_preserved_unchanged": v1_unchanged,
            }
        )

        logger.info(
            f"[Pilot 2] Completed unit {canonical_id} v2 in {latency_ms}ms (v1_id: {v1.version_id}, v2_id: {persisted_v2.version_id})."
        )

        if delay_between_requests > 0:
            time.sleep(delay_between_requests)

    return {
        "job_id": PILOT_JOB_ID,
        "total_units_translated": len(results),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "db_path": str(db_path),
        "results": results,
    }


def create_editorial_version_3(
    db_path: Path = DEFAULT_DB_PATH,
    storage: TranslationStorage | None = None,
) -> dict[str, Any]:
    """Create Version 3 as an editorial revision of the 5 pilot units.

    Applies specific editorial corrections to Version 2 while preserving
    Version 1 and Version 2 completely unchanged.

    Args:
        db_path: Path to the SQLite database.
        storage: Optional injected storage repository.

    Returns:
        Structured dictionary containing version 1, 2, and 3 records and
        verification confirmations.
    """
    if storage is None:
        storage = TranslationStorage(db_path)

    # Specific editorial texts per requirements
    editorial_revisions: dict[str, dict[str, Any]] = {
        "1.188": {
            "verse": (
                "Каусалья и другие возлюбленные жёны были чисты в своих деяниях; "
                "преданные своему супругу, они с непоколебимой любовью и смирением "
                "служили лотосным стопам Хари. || 188 ||"
            ),
            "commentary": None,
            "notes": (
                "Перевод выполнен строго по тексту оригинала на авадхи. "
                "«Kausalyādi nāri» (कौसल्यादि नारि) — Каусалья и другие жены. "
                "«Ācarana punīta» (आचरन पुनीत) — чистые в своих деяниях. "
                "«Pati anukūla» (पति अनुकूल) — верные, преданные супругу. "
                "«Prema dṛṛha» (प्रेम दृढ़) — с непоколебимой любовью. "
                "«Hari pada kamala binīta» (हरि पद कमल बिनीत) — со смирением служащие лотосным стопам Хари "
                "(термин «binīta» / санскр. «vinīta» выражает глубокое благоговение, кротость и смиренную преданность)."
            ),
        },
        "1.189.1": {
            # Keep Version 2 unchanged
            "use_v2_verse": True,
            "commentary": None,
            "notes": (
                "Перевод выполнен на основе оригинала на авадхи. «bhūpati» (भूपति) и «mahipālā» (महिपाला) "
                "переведены как «царь» и «владыка земли». «galāni» (गलानि) передает чувство душевной боли, "
                "угнетенности или печали от отсутствия потомства. «gura gṛha» (गुर गृह) — обитель гуру Васиштхи. "
                "«binaya bisālā» (बिनय बिсала) — усердные смиренные мольбы."
            ),
        },
        "1.189.2": {
            # Change «у тебя родится четверо сыновей» to «у тебя родятся четверо сыновей». Keep rest unchanged.
            "replace_rules": [("у тебя родится четверо сыновей", "у тебя родятся четверо сыновей")],
            "commentary": None,
            "notes": (
                "«Nija dukha sukha» — свои горести и радости. «Dharahu dhīra» — «сохраняй терпение», "
                "«храни стойкость» (букв. «удерживай терпение/мужество»). «Tribhuvana bidita» — известный "
                "в трех мирах. «Bhagata bhaya hārī» — устраняющие страхи преданных (бхакт)."
            ),
        },
        "1.189.3": {
            # Set russian_commentary to null. Keep the verse unchanged.
            # Do not assert that charu was rice porridge with milk unless supported by verified source.
            "use_v2_verse": True,
            "commentary": None,
            "notes": (
                "Оригинальные термины: «सृंगी रिषिहि» (sṛṁgī riṣihi) — риши Шринги; «बसिष्ठ» (basiṣṭha) — Васиштха; "
                "«पुत्रकाम सुभ जग्य» (putrakāma subha jagya) — благая ягья (жертвоприношение) ради рождения сына; "
                "«भगति सहित» (bhagati sahita) — с преданностью, бхакти; «आहुति» (āhuti) — ахути (ритуальное "
                "возлияние/подношение в жертвенный огонь); «प्रगटे अगिनि» (pragaṭe agini) — явился бог огня Агни (Агнидева); "
                "«चरू» (carū) — чару (священное жертвенное подношение, приготовленное для ягьи)."
            ),
        },
        "1.189.4": {
            "verse": (
                "Всё, что Васиштха замыслил в сердце своём, о царь, свершилось, и дело твоё "
                "увенчалось успехом. Ступай же и раздай это священное жертвенное подношение, "
                "разделив его на подобающие доли. || 4 ||"
            ),
            "commentary": None,
            "notes": (
                "Перевод выполнен на основе оригинала на авадхи. Фраза «jo basiṣṭha kachu hṛdayã bicārā / "
                "sakala kāju bhā siddha tumhārā» передает слова Агнидевы о том, что сокровенный замысел "
                "риши Васиштхи о даровании сыновей царю Дашаратхе полностью осуществился через явление священного дара. "
                "Слово «habi» (हबि / हवि, санскр. havis) обозначает сакральное жертвенное подношение, исходящее "
                "из жертвенного огня. Выражение «jathā joga jehi bhāga banāī» означает распределение священного "
                "дара на должные доли сообразно подобающему порядку."
            ),
        },
    }

    # Retrieve existing units that have both version 1 and version 2
    sql = """
    SELECT u.* FROM translation_units u
    JOIN translation_versions v ON u.unit_id = v.unit_id
    WHERE v.version_number = 2
    ORDER BY u.sequence_order ASC;
    """
    with storage.get_connection() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        raise ValueError(f"No existing units with version 2 found in '{db_path}'.")

    # Deduplicate distinct units
    seen_units: set[str] = set()
    pilot_units: list[TranslationUnitRecord] = []
    for r in rows:
        uid = r["unit_id"]
        if uid not in seen_units:
            seen_units.add(uid)
            pilot_units.append(storage._row_to_unit(r))

    pilot_units = pilot_units[:5]

    results: list[dict[str, Any]] = []

    for u in pilot_units:
        canonical_id = u.canonical_id
        if not canonical_id or canonical_id not in editorial_revisions:
            continue
        versions = storage.get_versions_for_unit(u.unit_id)
        if len(versions) < 2:
            raise ValueError(f"Unit {canonical_id} does not have both Version 1 and Version 2.")

        v1 = versions[0]
        v2 = versions[1]

        rule = editorial_revisions[canonical_id]

        # Determine verse text
        if rule.get("verse"):
            revised_verse = rule["verse"]
        elif rule.get("use_v2_verse"):
            revised_verse = v2.translated_verse_russian
        elif rule.get("replace_rules"):
            revised_verse = v2.translated_verse_russian
            for old_s, new_s in rule["replace_rules"]:
                revised_verse = revised_verse.replace(old_s, new_s)
        else:
            revised_verse = v2.translated_verse_russian

        revised_commentary = rule.get("commentary", None)
        revised_notes = rule.get("notes", v2.translator_notes)

        # Create Version 3 record identified as human editorial revision
        version_3_record = TranslationVersionRecord(
            unit_id=u.unit_id,
            source_stage=VersionStage.HUMAN_EDIT,
            translated_verse_russian=revised_verse,
            translated_commentary_russian=revised_commentary,
            translator_notes=revised_notes,
            confidence_assessment={
                "linguistic_certainty": "HIGH",
                "theological_clarity": "HIGH",
                "ambiguity_notes": None,
            },
            model_name=None,
            editor_id="human_editor",
            token_usage=None,
        )

        persisted_v3 = storage.create_version(u.unit_id, version_3_record)

        if persisted_v3.version_number != 3:
            raise ValueError(
                f"Expected version_number 3 for unit {canonical_id}, but got {persisted_v3.version_number}"
            )

        # Verify preservation of Version 1 and Version 2
        all_versions_after = storage.get_versions_for_unit(u.unit_id)
        v1_after = all_versions_after[0]
        v2_after = all_versions_after[1]
        v3_after = all_versions_after[2]

        v1_intact = (
            v1_after.version_id == v1.version_id
            and v1_after.version_number == 1
            and v1_after.translated_verse_russian == v1.translated_verse_russian
            and v1_after.source_stage == v1.source_stage
        )
        v2_intact = (
            v2_after.version_id == v2.version_id
            and v2_after.version_number == 2
            and v2_after.translated_verse_russian == v2.translated_verse_russian
            and v2_after.source_stage == v2.source_stage
        )

        results.append(
            {
                "canonical_id": canonical_id,
                "unit_id": u.unit_id,
                "unit_type": u.unit_type,
                "version_1_id": v1.version_id,
                "version_2_id": v2.version_id,
                "version_3_id": v3_after.version_id,
                "version_3_stage": v3_after.source_stage.value,
                "version_3_editor_id": v3_after.editor_id,
                "version_3_verse": v3_after.translated_verse_russian,
                "version_3_commentary": v3_after.translated_commentary_russian,
                "version_3_notes": v3_after.translator_notes,
                "v1_preserved": v1_intact,
                "v2_preserved": v2_intact,
                "created_at": v3_after.created_at.isoformat(),
            }
        )

        logger.info(
            f"[Editorial v3] Created Version 3 for {canonical_id} (v1: {v1.version_id}, v2: {v2.version_id}, v3: {v3_after.version_id})"
        )

    return {
        "job_id": PILOT_JOB_ID,
        "total_editorial_versions_created": len(results),
        "db_path": str(db_path),
        "results": results,
    }
