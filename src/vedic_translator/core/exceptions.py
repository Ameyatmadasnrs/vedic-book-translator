"""Domain exceptions hierarchy for Vedic Book Translator."""


class VedicTranslatorError(Exception):
    """Base exception for all Vedic Book Translator domain errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# Ingestion & Document Processing
class IngestionError(VedicTranslatorError):
    """Raised when document ingestion fails."""

    pass


class UnsupportedFormatError(IngestionError):
    """Raised when an unsupported file format is encountered."""

    pass


class CorruptedDocumentError(IngestionError):
    """Raised when an input document cannot be parsed or is corrupted."""

    pass


class OCREngineError(IngestionError):
    """Raised when OCR processing fails."""

    pass


# Structural & Semantic Segmentation
class SegmentationError(VedicTranslatorError):
    """Raised when document segmentation encounters structural defects."""

    pass


class MalformedVerseStructureError(SegmentationError):
    """Raised when canonical verse components cannot be aligned."""

    pass


class InconsistentVerseNumberingError(SegmentationError):
    """Raised when verse sequence numbers are discontinuous or duplicate."""

    pass


class ReferentialIntegrityError(SegmentationError):
    """Raised when document relationship references are invalid or broken."""

    pass


# AI Providers & Network
class ProviderError(VedicTranslatorError):
    """Raised when an external AI provider fails."""

    pass


class RateLimitExceededError(ProviderError):
    """Raised when an AI provider responds with HTTP 429."""

    pass


class AuthenticationError(ProviderError):
    """Raised when API key or authentication is invalid."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when an AI provider request times out."""

    pass


# Pipeline Execution
class PipelineError(VedicTranslatorError):
    """Raised when a translation pipeline stage fails."""

    pass


class StageExecutionError(PipelineError):
    """Raised when an individual transformation stage fails."""

    pass


class ContextInjectionError(PipelineError):
    """Raised when book or chapter context cannot be prepared."""

    pass


# Quality Control & Auditing
class QualityControlError(VedicTranslatorError):
    """Raised when a block fails quality control audits."""

    pass


class TerminologyViolationError(QualityControlError):
    """Raised when forbidden or inconsistent terminology is detected."""

    pass


class MissingDiacriticsError(QualityControlError):
    """Raised when required Sanskrit diacritical marks are missing or corrupt."""

    pass


class HallucinationDetectedError(QualityControlError):
    """Raised when anomalous length or unverified claims are detected."""

    pass


# Publishing Engine
class PublishingError(VedicTranslatorError):
    """Raised when exporting to target publication formats fails."""

    pass


class FontEmbeddingError(PublishingError):
    """Raised when required Devanagari or Cyrillic fonts cannot be embedded."""

    pass


class ExportValidationError(PublishingError):
    """Raised when exported publication file fails validation (e.g., epubcheck)."""

    pass
