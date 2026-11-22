"""Document Processor Subsystem: Ingestion, Digital Extractors, and AST Modeling."""

from vedic_translator.document_processor.extractors import (
    BaseExtractor,
    DocumentExtractor,
    DOCXExtractor,
    EPUBExtractor,
    PDFExtractor,
    TXTExtractor,
)

__all__ = [
    "BaseExtractor",
    "DocumentExtractor",
    "DOCXExtractor",
    "EPUBExtractor",
    "PDFExtractor",
    "TXTExtractor",
]
