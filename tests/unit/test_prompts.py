"""Unit tests for the revised Ramcharit Manas translation prompt and output structure."""

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vedic_translator.core.exceptions import ProviderError
from vedic_translator.translation_engine.prompts import (
    RAMCHARIT_MANAS_SYSTEM_PROMPT,
    build_ramcharit_manas_system_instruction,
)
from vedic_translator.translation_engine.providers.base import (
    TranslationPayload,
)
from vedic_translator.translation_engine.providers.gemini import (
    DEFAULT_SYSTEM_INSTRUCTION,
    GeminiTranslationProvider,
)


def test_prompt_contains_all_core_requirements() -> None:
    """Verify that RAMCHARIT_MANAS_SYSTEM_PROMPT explicitly embodies all 10 directives."""
    prompt = RAMCHARIT_MANAS_SYSTEM_PROMPT

    # 1. Awadhi primacy
    assert "<ORIGINAL_SOURCE>" in prompt
    assert "Awadhi" in prompt
    assert "sole authoritative" in prompt or "authoritative and foundational" in prompt

    # 2. Subordinate role of English reference (negative constraint against English translation)
    assert "<ENGLISH_REFERENCE>" in prompt
    assert "Gita Press" in prompt
    assert "NEVER translate from the English" in prompt
    assert "English calques" in prompt

    # 3. Line-by-line semantic preservation
    assert "every line" in prompt or "every line, half-line" in prompt
    assert "|| 188 ||" in prompt

    # 4. No extra-textual theological or historical claims in verse translation
    assert 'The verse translation ("russian_verse") must contain ONLY' in prompt
    assert "Do NOT inject unstated theological doctrines" in prompt
    assert "avataras" in prompt

    # 5. Strict separation of translation, notes, and commentary
    assert '"russian_verse"' in prompt
    assert '"russian_commentary"' in prompt
    assert '"translator_notes"' in prompt
    assert '"confidence_assessment"' in prompt
    assert "strictly separate" in prompt

    # 6. Explicit ambiguity identification instead of inventing confident interpretations
    assert "Do NOT invent a single confident interpretation" in prompt
    assert "ambiguity_notes" in prompt
    assert "MEDIUM" in prompt and "LOW" in prompt

    # 7. Natural literary Russian & devotional tone
    assert "высокий литературный стиль" in prompt
    assert "bhakti-bhāva" in prompt or "bhakti" in prompt
    assert "Всевышний" in prompt and "Господь" in prompt

    # 8. Sanskrit & Vaishnava technical terms
    assert "риши" in prompt and "чару" in prompt
    assert "лотосные стопы" in prompt
    assert "Хари" in prompt and "Васиштха" in prompt

    # 9. IAST as supporting evidence only
    assert "<IAST_TRANSLITERATION>" in prompt
    assert "Do NOT mechanically translate the IAST" in prompt

    # 10. Specific pilot pitfall corrections:
    # 10a. dharahu dhira -> patience, composure, courage, NOT wisdom
    assert "dharahu dhīra" in prompt
    assert "мудрость" in prompt
    assert "терпение" in prompt or "стойкость" in prompt

    # 10b. habi/havis -> sacrificial offering, no invented substance
    assert "habi" in prompt or "havis" in prompt
    assert "sacrificial offering" in prompt or "жертвенное" in prompt
    assert "Do NOT invent or specify an unstated substance" in prompt

    # 10c. Four sons -> no theological claims in literal verse
    assert "suta cārī" in prompt


def test_build_ramcharit_manas_system_instruction() -> None:
    """Verify system instruction builder with and without supplementary directives."""
    base = build_ramcharit_manas_system_instruction()
    assert base == RAMCHARIT_MANAS_SYSTEM_PROMPT.strip()

    supplemented = build_ramcharit_manas_system_instruction("Focus on chaupai meter.")
    assert "Focus on chaupai meter." in supplemented
    assert "SUPPLEMENTARY DIRECTIVES:" in supplemented
    assert RAMCHARIT_MANAS_SYSTEM_PROMPT.strip() in supplemented


def test_gemini_provider_defaults_to_revised_prompt() -> None:
    """Verify GeminiTranslationProvider default system instruction is the revised prompt."""
    assert DEFAULT_SYSTEM_INSTRUCTION == RAMCHARIT_MANAS_SYSTEM_PROMPT

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "1.189.2",
            "russian_verse": (
                "Он поведал Гуру обо всех своих горестях и радостях; мудрый Васиштха "
                "утешил его многими речами: «Храни терпение, родятся у тебя четыре сына, "
                "прославленные в трех мирах, что рассеивают страх преданных». || 2 ||"
            ),
            "russian_commentary": "Мудрец Васиштха утешает царя Дашаратху.",
            "translator_notes": "Слово 'dhīra' передано как 'терпение / стойкость'.",
            "confidence_assessment": {
                "linguistic_certainty": "HIGH",
                "theological_clarity": "HIGH",
                "ambiguity_notes": None,
            },
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="mock-key", client=mock_client)
    payload = TranslationPayload(
        unit_id=uuid4(),
        canonical_id="1.189.2",
        original_text="धरहु धीर होइहहिं सुत चारी। त्रिभुवन बिदित भगत भय हारी॥ 2॥",
    )

    response = provider.translate(payload)

    # Verify that the revised prompt was forwarded in system_instruction
    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert call_kwargs["system_instruction"] == RAMCHARIT_MANAS_SYSTEM_PROMPT
    assert response.canonical_id == "1.189.2"
    assert "Храни терпение" in response.russian_verse
    assert response.confidence_assessment.linguistic_certainty == "HIGH"
    assert response.confidence_assessment.ambiguity_notes is None


def test_output_structure_parses_ambiguity_notes() -> None:
    """Verify that response with explicit ambiguity notes parses cleanly into DTO."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "1.189.4",
            "russian_verse": (
                "То, о чем Васиштха помыслил в сердце своем, — все дело твое увенчалось успехом. "
                "Ступай же, о царь, и раздай это священное подношение по подобающим долям. || 4 ||"
            ),
            "russian_commentary": None,
            "translator_notes": (
                "Слово 'habi' (санскр. havis) обозначает сакральное жертвенное приношение. "
                "Его точный состав в стихе не специфицирован."
            ),
            "confidence_assessment": {
                "linguistic_certainty": "MEDIUM",
                "theological_clarity": "HIGH",
                "ambiguity_notes": (
                    "Слово 'habi' допускает более общее толкование как жертвенное масло "
                    "или более частное как чару."
                ),
            },
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="mock-key", client=mock_client)
    payload = TranslationPayload(
        unit_id=uuid4(),
        canonical_id="1.189.4",
        original_text="यह हबि बाँटि देहु नृप जाई। जथा जोग जेहि भाग बनाई॥ 4॥",
    )

    response = provider.translate(payload)
    assert response.russian_commentary is None
    assert response.translator_notes is not None
    assert "havis" in response.translator_notes
    assert response.confidence_assessment.linguistic_certainty == "MEDIUM"
    assert response.confidence_assessment.ambiguity_notes is not None
    assert "чару" in response.confidence_assessment.ambiguity_notes


def test_output_structure_enforces_required_fields() -> None:
    """Verify that response missing 'russian_verse' raises ProviderError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    # Malformed response missing 'russian_verse'
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "1.188",
            "russian_commentary": "Some commentary without verse translation.",
            "translator_notes": "Some notes.",
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="mock-key", client=mock_client)
    payload = TranslationPayload(
        unit_id=uuid4(),
        canonical_id="1.188",
        original_text="कौसल्यादि नारि प्रिय सब आचरन पुनीत॥ 188॥",
    )

    with pytest.raises(ProviderError, match="missing required 'russian_verse' field"):
        provider.translate(payload)


def test_output_structure_rejects_non_dict_root() -> None:
    """Verify that non-object JSON root raises ProviderError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(["array", "of", "items"])
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="mock-key", client=mock_client)
    payload = TranslationPayload(
        unit_id=uuid4(),
        canonical_id="1.188",
        original_text="कौसल्यादि नारि प्रिय सब आचरन पुनीत॥ 188॥",
    )

    with pytest.raises(ProviderError, match="JSON root must be an object"):
        provider.translate(payload)


def test_prompt_commentary_null_when_unsupplied() -> None:
    """Verify that commentary is explicitly set to null when no source commentary exists."""
    prompt = RAMCHARIT_MANAS_SYSTEM_PROMPT
    assert 'set "russian_commentary" to null' in prompt
    assert (
        "Do not invent traditional interpretations, scriptural references, historical details, "
        "or theological explanations"
    ) in prompt


def test_prompt_glossary_conditional_application() -> None:
    """Verify that glossary instructions apply only when supplied, without fabricated entries."""
    prompt = RAMCHARIT_MANAS_SYSTEM_PROMPT
    assert "Apply <GLOSSARY> instructions only when glossary data is actually supplied" in prompt
    assert (
        "Never invent glossary entries or claim that a term is an established BBT preference "
        "without evidence"
    ) in prompt


def test_prompt_vocabulary_no_unconditional_prohibitions() -> None:
    """Verify that specific Russian words are not unconditionally banned."""
    prompt = RAMCHARIT_MANAS_SYSTEM_PROMPT
    # Verify unconditional prohibitions are removed
    assert 'do not use "грех"' not in prompt
    assert '"молитвенник"' not in prompt
    assert '"спасение души"' not in prompt
    assert '"поп"' not in prompt

    # Verify contextual requirement is present
    assert "Aim for accurate contextual translation" in prompt
    assert "avoiding inappropriate terminology only when it distorts the original meaning" in prompt
