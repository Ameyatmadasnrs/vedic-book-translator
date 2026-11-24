"""Unit tests for MVP B pilot translation module using mocked provider."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vedic_translator.translation_engine.pilot import (
    create_editorial_version_3,
    execute_pilot,
    execute_second_pilot,
    extract_pilot_units,
)
from vedic_translator.translation_engine.providers.base import (
    ConfidenceAssessment,
    TokenUsage,
    TranslationPayload,
    TranslationResponse,
)
from vedic_translator.translation_engine.storage import JobStatus, TranslationStorage, UnitStatus


@pytest.fixture
def mock_gemini_provider() -> MagicMock:
    """Mock GeminiTranslationProvider to simulate API responses without network calls."""
    provider = MagicMock()
    provider.provider_name = "gemini"

    def fake_translate(payload: TranslationPayload, config=None) -> TranslationResponse:
        return TranslationResponse(
            canonical_id=payload.canonical_id,
            russian_verse=f"Тестовый русский перевод стиха {payload.canonical_id}",
            russian_commentary=None,
            translator_notes="Тестовые примечания переводчика",
            confidence_assessment=ConfidenceAssessment(
                linguistic_certainty="HIGH",
                theological_clarity="HIGH",
            ),
            model_name="gemini-3.5-flash-lite",
            token_usage=TokenUsage(
                input_tokens=150,
                output_tokens=50,
                total_tokens=200,
            ),
        )

    provider.translate.side_effect = fake_translate
    return provider


def test_extract_pilot_units_real_pdf() -> None:
    """Verify that extract_pilot_units successfully loads the 5 target units from the real book PDF."""
    pdf_path = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not pdf_path.exists():
        pytest.skip("Test book PDF not found.")

    units = extract_pilot_units(pdf_path)
    assert len(units) == 5
    assert units[0]["canonical_id"] == "1.188"
    assert units[0]["unit_type"] == "DOHA"
    assert "कौसल्यादि" in units[0]["original_text"]

    assert units[1]["canonical_id"] == "1.189.1"
    assert units[1]["unit_type"] == "CHAUPAI"
    assert "भूपति" in units[1]["original_text"] and "सुत" in units[1]["original_text"]

    assert units[4]["canonical_id"] == "1.189.4"
    assert units[4]["unit_type"] == "CHAUPAI"
    assert "बसिष्ठ" in units[4]["original_text"]


def test_execute_pilot_mocked(tmp_path: Path, mock_gemini_provider: MagicMock) -> None:
    """Verify end-to-end pilot execution, SQLite persistence, and state transitions with mocked provider."""
    pdf_path = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not pdf_path.exists():
        pytest.skip("Test book PDF not found.")

    db_path = tmp_path / "test_pilot_mock.db"
    storage = TranslationStorage(db_path)

    result = execute_pilot(
        pdf_path=pdf_path,
        db_path=db_path,
        provider=mock_gemini_provider,
        storage=storage,
        delay_between_requests=0.0,
    )

    assert result["total_units_translated"] == 5
    assert result["job_status"] == JobStatus.COMPLETED.value
    assert result["total_tokens"] == 1000

    # Verify storage records
    job = storage.get_job(result["job_id"])
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.completed_units == 5

    stored_units = storage.get_units_for_job(job.job_id)
    assert len(stored_units) == 5
    for u in stored_units:
        assert u.status == UnitStatus.TRANSLATED
        versions = storage.get_versions_for_unit(u.unit_id)
        assert len(versions) == 1
        assert "Тестовый русский перевод" in versions[0].translated_verse_russian
        assert versions[0].model_name == "gemini-3.5-flash-lite"


def test_execute_second_pilot_mocked(tmp_path: Path, mock_gemini_provider: MagicMock) -> None:
    """Verify that execute_second_pilot preserves version 1 and produces version 2."""
    pdf_path = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not pdf_path.exists():
        pytest.skip("Test book PDF not found.")

    db_path = tmp_path / "test_pilot_v2_mock.db"
    storage = TranslationStorage(db_path)

    # First run pilot 1 to create version 1
    execute_pilot(
        pdf_path=pdf_path,
        db_path=db_path,
        provider=mock_gemini_provider,
        storage=storage,
        delay_between_requests=0.0,
    )

    # Run pilot 2 with a modified mock response to distinguish v2
    def fake_translate_v2(payload: TranslationPayload, config=None) -> TranslationResponse:
        return TranslationResponse(
            canonical_id=payload.canonical_id,
            russian_verse=f"Вторая версия русского перевода {payload.canonical_id}",
            russian_commentary=None,
            translator_notes="Примечания версии 2",
            confidence_assessment=ConfidenceAssessment(
                linguistic_certainty="HIGH",
                theological_clarity="HIGH",
            ),
            model_name="gemini-3.5-flash-lite",
            token_usage=TokenUsage(
                input_tokens=160,
                output_tokens=60,
                total_tokens=220,
            ),
        )

    mock_gemini_provider.translate.side_effect = fake_translate_v2

    res_v2 = execute_second_pilot(
        db_path=db_path,
        provider=mock_gemini_provider,
        storage=storage,
        delay_between_requests=0.0,
    )

    assert res_v2["total_units_translated"] == 5
    for item in res_v2["results"]:
        assert item["v1_preserved_unchanged"] is True
        assert item["version_1"]["version_number"] == 1
        assert "Тестовый русский перевод" in item["version_1"]["russian_verse"]
        assert item["version_2"]["version_number"] == 2
        assert "Вторая версия русского перевода" in item["version_2"]["russian_verse"]
        assert item["version_1"]["version_id"] != item["version_2"]["version_id"]

        # Also verify directly from storage
        all_v = storage.get_versions_for_unit(item["unit_id"])
        assert len(all_v) == 2
        assert all_v[0].version_number == 1
        assert all_v[1].version_number == 2


def test_create_editorial_version_3_mocked(tmp_path: Path, mock_gemini_provider: MagicMock) -> None:
    """Verify that create_editorial_version_3 preserves versions 1 and 2 and creates version 3."""
    pdf_path = Path("data/test_books/Ramcharita_Manas_Gita_Press.pdf")
    if not pdf_path.exists():
        pytest.skip("Test book PDF not found.")

    db_path = tmp_path / "test_pilot_v3_mock.db"
    storage = TranslationStorage(db_path)

    # 1. Run pilot 1
    execute_pilot(
        pdf_path=pdf_path,
        db_path=db_path,
        provider=mock_gemini_provider,
        storage=storage,
        delay_between_requests=0.0,
    )

    # 2. Run pilot 2
    def fake_translate_v2(payload: TranslationPayload, config=None) -> TranslationResponse:
        return TranslationResponse(
            canonical_id=payload.canonical_id,
            russian_verse=(
                "у тебя родится четверо сыновей"
                if payload.canonical_id == "1.189.2"
                else f"Вторая версия {payload.canonical_id}"
            ),
            russian_commentary="Старый комментарий" if payload.canonical_id == "1.189.3" else None,
            translator_notes="Старые примечания",
            confidence_assessment=ConfidenceAssessment(
                linguistic_certainty="HIGH",
                theological_clarity="HIGH",
            ),
            model_name="gemini-3.5-flash-lite",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )

    mock_gemini_provider.translate.side_effect = fake_translate_v2

    execute_second_pilot(
        db_path=db_path,
        provider=mock_gemini_provider,
        storage=storage,
        delay_between_requests=0.0,
    )

    # 3. Create Version 3 editorial revision
    res_v3 = create_editorial_version_3(db_path=db_path, storage=storage)

    assert res_v3["total_editorial_versions_created"] == 5

    # Check unit 1.188
    u188 = next(r for r in res_v3["results"] if r["canonical_id"] == "1.188")
    assert "были чисты в своих деяниях" in u188["version_3_verse"]
    assert u188["version_3_stage"] == "HUMAN_EDIT"
    assert u188["v1_preserved"] is True
    assert u188["v2_preserved"] is True

    # Check unit 1.189.2 grammar correction
    u189_2 = next(r for r in res_v3["results"] if r["canonical_id"] == "1.189.2")
    assert "у тебя родятся четверо сыновей" in u189_2["version_3_verse"]
    assert "родится" not in u189_2["version_3_verse"]

    # Check unit 1.189.3 commentary is null
    u189_3 = next(r for r in res_v3["results"] if r["canonical_id"] == "1.189.3")
    assert u189_3["version_3_commentary"] is None

    # Check unit 1.189.4 verse replaced
    u189_4 = next(r for r in res_v3["results"] if r["canonical_id"] == "1.189.4")
    assert "дело твоё увенчалось успехом" in u189_4["version_3_verse"]
    assert "[из цариц]" not in u189_4["version_3_verse"]

    # Verify each unit now has 3 versions in storage
    for item in res_v3["results"]:
        all_v = storage.get_versions_for_unit(item["unit_id"])
        assert len(all_v) == 3
        assert all_v[0].version_number == 1
        assert all_v[1].version_number == 2
        assert all_v[2].version_number == 3
        assert all_v[2].source_stage.value == "HUMAN_EDIT"
        assert all_v[2].editor_id == "human_editor"
