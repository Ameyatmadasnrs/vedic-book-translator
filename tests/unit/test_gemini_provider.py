"""Unit tests for GeminiTranslationProvider with mocked Google GenAI SDK interactions."""

import json
from unittest.mock import MagicMock

import pytest

from vedic_translator.core.exceptions import (
    AuthenticationError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitExceededError,
)
from vedic_translator.translation_engine.providers.base import (
    ContextItem,
    GlossaryTerm,
    ProviderConfig,
    TranslationPayload,
)
from vedic_translator.translation_engine.providers.gemini import (
    DEFAULT_GEMINI_MODEL,
    GeminiTranslationProvider,
)


@pytest.fixture
def sample_payload() -> TranslationPayload:
    """Fixture returning a standard dummy translation payload (unrelated to full book)."""
    return TranslationPayload(
        canonical_id="test.1.1",
        unit_type="DOHA",
        original_text="श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।",
        transliteration="śrīguru carana saroja raja nija manu mukuru sudhāri |",
        reference_translation="Cleansing the mirror of my mind with the dust of the guru's lotus feet.",
        commentary="Introductory invocatory prayer.",
        canto_name="Bala Kanda",
        narrative_episode="Invocation",
        active_speakers="Narration",
        glossary_terms=[
            GlossaryTerm(
                term="Guru",
                canonical_russian="Гуру",
                declensions={"gen": "Гуру", "dat": "Гуру"},
                notes="Spiritual master",
            )
        ],
        preceding_context=[
            ContextItem(canonical_id="test.1.0", russian_verse="Начало святого повествования...")
        ],
    )


def test_missing_api_key_raises_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify instantiating provider without an API key or env var raises AuthenticationError."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="GEMINI_API_KEY is not configured"):
        GeminiTranslationProvider()


def test_provider_metadata_and_custom_model() -> None:
    """Verify provider name, default model, and custom model configuration."""
    mock_client = MagicMock()
    provider = GeminiTranslationProvider(
        api_key="dummy_key",
        default_model="gemini-3.5-flash-lite",
        client=mock_client,
    )
    assert provider.provider_name == "gemini"
    assert provider.default_model == "gemini-3.5-flash-lite"

    custom_provider = GeminiTranslationProvider(
        api_key="dummy_key",
        default_model="custom-model-id",
        client=mock_client,
    )
    assert custom_provider.default_model == "custom-model-id"


def test_translate_successful_response(sample_payload: TranslationPayload) -> None:
    """Verify translate() correctly invokes interactions.create and parses JSON output."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()

    json_payload = {
        "canonical_id": "test.1.1",
        "russian_verse": "Очистив зеркало своего ума пыльцой с лотосных стоп духовного учителя...",
        "russian_commentary": "Вводная молитва благословения.",
        "translator_notes": "Слово 'мукуру' обозначает зеркало.",
        "confidence_assessment": {
            "linguistic_certainty": "HIGH",
            "theological_clarity": "HIGH",
            "ambiguity_notes": None,
        },
    }
    mock_interaction.output_text = json.dumps(json_payload)
    mock_interaction.usage.total_input_tokens = 45
    mock_interaction.usage.total_output_tokens = 32
    mock_interaction.usage.total_tokens = 77
    mock_interaction.usage.total_cached_tokens = 0

    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    response = provider.translate(sample_payload)

    # Verify call parameters
    mock_client.interactions.create.assert_called_once()
    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert call_kwargs["model"] == DEFAULT_GEMINI_MODEL
    assert call_kwargs["system_instruction"] is not None
    assert "<CANONICAL_ID>test.1.1</CANONICAL_ID>" in call_kwargs["input"]
    assert "śrīguru carana saroja" in call_kwargs["input"]
    assert "Гуру" in call_kwargs["input"]

    # Verify parsed response
    assert response.canonical_id == "test.1.1"
    assert response.russian_verse.startswith("Очистив зеркало")
    assert response.russian_commentary == "Вводная молитва благословения."
    assert response.translator_notes == "Слово 'мукуру' обозначает зеркало."
    assert response.confidence_assessment.linguistic_certainty == "HIGH"
    assert response.model_name == DEFAULT_GEMINI_MODEL
    assert response.token_usage is not None
    assert response.token_usage.total_tokens == 77


def test_translate_markdown_code_fence_cleaning(sample_payload: TranslationPayload) -> None:
    """Verify translate() cleans markdown ```json wrappers around JSON responses."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()

    inner_json = json.dumps(
        {
            "canonical_id": "test.1.1",
            "russian_verse": "Стих в разметке markdown.",
            "confidence_assessment": {
                "linguistic_certainty": "HIGH",
                "theological_clarity": "HIGH",
            },
        }
    )
    mock_interaction.output_text = f"```json\n{inner_json}\n```"
    mock_interaction.usage = None
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    response = provider.translate(sample_payload)

    assert response.russian_verse == "Стих в разметке markdown."
    assert response.token_usage is None


def test_translate_per_request_config_override(sample_payload: TranslationPayload) -> None:
    """Verify ProviderConfig overrides model name on a per-request basis."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "test.1.1",
            "russian_verse": "Тест переопределения модели.",
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    override_config = ProviderConfig(model="gemini-custom-pro")
    response = provider.translate(sample_payload, config=override_config)

    assert response.model_name == "gemini-custom-pro"
    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-custom-pro"


def test_translate_stepped_interaction_fallback(sample_payload: TranslationPayload) -> None:
    """Verify fallback text extraction when output_text is None but interaction contains steps."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = None

    # Mock steps structure
    step1 = MagicMock()
    step1.type = "model_output"
    item1 = MagicMock()
    item1.type = "text"
    item1.text = json.dumps(
        {
            "canonical_id": "test.1.1",
            "russian_verse": "Стих из ступенчатого ответа.",
        }
    )
    step1.content = [item1]
    mock_interaction.steps = [step1]
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    response = provider.translate(sample_payload)

    assert response.russian_verse == "Стих из ступенчатого ответа."


def test_translate_empty_response_raises_provider_error(sample_payload: TranslationPayload) -> None:
    """Verify empty response text raises ProviderError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = "   "
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError, match="Empty response received"):
        provider.translate(sample_payload)


def test_translate_malformed_json_raises_provider_error(sample_payload: TranslationPayload) -> None:
    """Verify malformed JSON raises ProviderError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = "Internal error: not a json response"
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError, match="Failed to parse JSON response"):
        provider.translate(sample_payload)


def test_translate_missing_russian_verse_raises_provider_error(
    sample_payload: TranslationPayload,
) -> None:
    """Verify JSON missing 'russian_verse' raises ProviderError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {"canonical_id": "test.1.1", "notes": "No verse provided"}
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError, match="missing required 'russian_verse'"):
        provider.translate(sample_payload)


def test_api_authentication_error_mapping(sample_payload: TranslationPayload) -> None:
    """Verify HTTP 401 / 403 maps to domain AuthenticationError."""
    mock_client = MagicMock()
    api_exc = Exception("API key not valid. Please pass a valid API key.")
    api_exc.status_code = 401
    mock_client.interactions.create.side_effect = api_exc

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(AuthenticationError, match="Gemini authentication failed"):
        provider.translate(sample_payload)


def test_api_rate_limit_error_mapping(sample_payload: TranslationPayload) -> None:
    """Verify HTTP 429 maps to domain RateLimitExceededError."""
    mock_client = MagicMock()
    api_exc = Exception("Resource has been exhausted (e.g. check quota).")
    api_exc.status_code = 429
    mock_client.interactions.create.side_effect = api_exc

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(RateLimitExceededError, match="Gemini rate limit exceeded"):
        provider.translate(sample_payload)


def test_api_timeout_error_mapping(sample_payload: TranslationPayload) -> None:
    """Verify timeout exception maps to domain ProviderTimeoutError."""
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = TimeoutError(
        "The connection timed out after 30.0s"
    )

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderTimeoutError, match="Gemini request timed out"):
        provider.translate(sample_payload)


def test_secret_sanitization_in_error_message(sample_payload: TranslationPayload) -> None:
    """Verify API key is never leaked in mapped exceptions even if present in raw error."""
    secret_key = "AIzaSySECRET_API_KEY_12345"
    mock_client = MagicMock()
    raw_error_message = f"Call failed with header x-goog-api-key={secret_key}: backend failed"
    mock_client.interactions.create.side_effect = RuntimeError(raw_error_message)

    provider = GeminiTranslationProvider(api_key=secret_key, client=mock_client)
    with pytest.raises(ProviderError) as exc_info:
        provider.translate(sample_payload)

    err_str = str(exc_info.value)
    assert secret_key not in err_str
    assert "[REDACTED_API_KEY]" in err_str


def test_validate_connection_success() -> None:
    """Verify validate_connection() returns OK on successful interaction."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = "GEMINI_API_CONNECTION_OK"
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    health = provider.validate_connection()

    assert health.status == "OK"
    assert health.provider_name == "gemini"
    assert health.model_name == DEFAULT_GEMINI_MODEL
    assert health.latency_ms is not None
    assert health.latency_ms >= 0.0
    assert health.details["response_text"] == "GEMINI_API_CONNECTION_OK"


def test_validate_connection_failure_redacts_secret() -> None:
    """Verify validate_connection() catches errors, redacts secrets, and returns ERROR status."""
    secret_key = "AIzaSySECRET999"
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = RuntimeError(
        f"Connection failed for key {secret_key}"
    )

    provider = GeminiTranslationProvider(api_key=secret_key, client=mock_client)
    health = provider.validate_connection()

    assert health.status == "ERROR"
    assert health.provider_name == "gemini"
    assert secret_key not in str(health.details)
    assert "[REDACTED_API_KEY]" in health.details["error"]


def test_translate_configuration_full_forwarding(sample_payload: TranslationPayload) -> None:
    """Verify all supported ProviderConfig options are forwarded to interactions.create."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "test.1.1",
            "russian_verse": "Стих с полной конфигурацией.",
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    config = ProviderConfig(
        model="gemini-custom-pro",
        temperature=0.7,
        max_output_tokens=1024,
        timeout_seconds=45.0,
    )
    provider.translate(sample_payload, config=config)

    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-custom-pro"
    assert call_kwargs["timeout"] == 45.0
    assert call_kwargs["generation_config"] == {
        "temperature": 0.7,
        "max_output_tokens": 1024,
    }


def test_translate_configuration_partial_forwarding(sample_payload: TranslationPayload) -> None:
    """Verify partial configuration forwards only set values."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(
        {
            "canonical_id": "test.1.1",
            "russian_verse": "Стих с частичной конфигурацией.",
        }
    )
    mock_client.interactions.create.return_value = mock_interaction

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    config = ProviderConfig(temperature=0.0)
    provider.translate(sample_payload, config=config)

    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert "timeout" in call_kwargs  # default timeout_seconds is 30.0 in ProviderConfig
    assert call_kwargs["timeout"] == 30.0
    assert call_kwargs["generation_config"] == {"temperature": 0.0}
    assert "max_output_tokens" not in call_kwargs["generation_config"]


def test_api_transient_error_http_503(sample_payload: TranslationPayload) -> None:
    """Verify HTTP 503 is mapped to ProviderError with is_transient=True."""
    mock_client = MagicMock()
    api_exc = Exception("The server is temporarily overloaded. Please try again.")
    api_exc.status_code = 503
    mock_client.interactions.create.side_effect = api_exc

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError) as exc_info:
        provider.translate(sample_payload)

    details = exc_info.value.details
    assert details.get("status_code") == 503
    assert details.get("is_transient") is True


def test_api_transient_error_service_unavailable_string(sample_payload: TranslationPayload) -> None:
    """Verify service_unavailable error text is mapped with is_transient=True."""
    mock_client = MagicMock()
    raw_msg = (
        "Error code: 503 - {'error': {'message': "
        "'gemini-3.8-flash is currently experiencing high demand', 'code': 'service_unavailable'}}"
    )
    mock_client.interactions.create.side_effect = Exception(raw_msg)

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError) as exc_info:
        provider.translate(sample_payload)

    details = exc_info.value.details
    assert details.get("is_transient") is True


def test_api_non_transient_error_permanent(sample_payload: TranslationPayload) -> None:
    """Verify permanent errors (e.g. HTTP 400 Bad Request) are NOT tagged as transient."""
    mock_client = MagicMock()
    api_exc = Exception("Invalid argument: model parameter malformed")
    api_exc.status_code = 400
    mock_client.interactions.create.side_effect = api_exc

    provider = GeminiTranslationProvider(api_key="dummy_key", client=mock_client)
    with pytest.raises(ProviderError) as exc_info:
        provider.translate(sample_payload)

    details = exc_info.value.details
    assert details.get("status_code") == 400
    assert "is_transient" not in details
