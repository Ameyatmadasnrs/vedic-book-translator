"""Core module containing foundational models, exceptions, and configuration."""

from vedic_translator.core.exceptions import (
    IngestionError,
    PipelineError,
    ProviderError,
    PublishingError,
    QualityControlError,
    ReferentialIntegrityError,
    SegmentationError,
    VedicTranslatorError,
)
from vedic_translator.core.models import (
    AlternativeClassification,
    Block,
    BlockState,
    BlockType,
    Chapter,
    ClassificationProvenance,
    Document,
    DocumentMetadata,
    Section,
    StageAudit,
)

__all__ = [
    "VedicTranslatorError",
    "IngestionError",
    "SegmentationError",
    "ReferentialIntegrityError",
    "ProviderError",
    "PipelineError",
    "QualityControlError",
    "PublishingError",
    "AlternativeClassification",
    "Block",
    "BlockState",
    "BlockType",
    "Chapter",
    "ClassificationProvenance",
    "Document",
    "DocumentMetadata",
    "Section",
    "StageAudit",
]
