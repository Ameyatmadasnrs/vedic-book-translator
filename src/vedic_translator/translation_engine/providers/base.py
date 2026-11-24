"""Provider-agnostic abstract interface and data structures for translation engine."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token consumption metrics for a single translation request."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class ConfidenceAssessment(BaseModel):
    """Model self-reported confidence and ambiguity indicators."""

    linguistic_certainty: str = "HIGH"  # HIGH, MEDIUM, LOW
    theological_clarity: str = "HIGH"  # HIGH, MEDIUM, LOW
    ambiguity_notes: str | None = None


class GlossaryTerm(BaseModel):
    """A matched theological or character term to constrain translation."""

    term: str
    canonical_russian: str
    declensions: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None


class ContextItem(BaseModel):
    """Preceding translated unit for sliding-window continuity."""

    canonical_id: str | None = None
    russian_verse: str


class TranslationPayload(BaseModel):
    """Self-contained input payload representing a single unit to be translated."""

    unit_id: UUID = Field(default_factory=uuid4)
    canonical_id: str | None = None
    unit_type: str = "GENERIC_VERSE"
    original_text: str
    transliteration: str | None = None
    reference_translation: str | None = None
    commentary: str | None = None
    canto_name: str | None = None
    narrative_episode: str | None = None
    active_speakers: str | None = None
    glossary_terms: list[GlossaryTerm] = Field(default_factory=list)
    preceding_context: list[ContextItem] = Field(default_factory=list)
    system_instruction: str | None = None
    custom_instructions: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranslationResponse(BaseModel):
    """Normalized structured response produced by any translation provider."""

    canonical_id: str | None = None
    russian_verse: str
    russian_commentary: str | None = None
    translator_notes: str | None = None
    confidence_assessment: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)
    model_name: str
    token_usage: TokenUsage | None = None
    raw_response: str | None = None


class ProviderConfig(BaseModel):
    """Optional per-request configuration overrides."""

    model: str | None = None
    temperature: float = 0.2
    max_output_tokens: int | None = None
    timeout_seconds: float = 30.0


class ProviderHealthCheck(BaseModel):
    """Standardized health check result from validating connection."""

    provider_name: str
    model_name: str
    status: str  # "OK" or "ERROR"
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ITranslationProvider(ABC):
    """Abstract provider port decoupling the translation pipeline from AI vendors."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique provider name (e.g. 'gemini', 'anthropic', 'openai')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model name configured for this provider."""
        ...

    @abstractmethod
    def translate(
        self,
        payload: TranslationPayload,
        config: ProviderConfig | None = None,
    ) -> TranslationResponse:
        """Translate a single unit payload into the target language."""
        ...

    @abstractmethod
    def validate_connection(self) -> ProviderHealthCheck:
        """Perform a minimal health check to verify credentials and connectivity."""
        ...
