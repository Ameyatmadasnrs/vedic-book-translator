"""Format-specific extractors for digital PDF, EPUB, DOCX, and TXT files."""

from vedic_translator.document_processor.extractors.base import (
    BaseExtractor,
    compute_file_sha256,
    validate_source_file,
)
from vedic_translator.document_processor.extractors.docx import DOCXExtractor
from vedic_translator.document_processor.extractors.epub import EPUBExtractor
from vedic_translator.document_processor.extractors.factory import DocumentExtractor
from vedic_translator.document_processor.extractors.pdf import PDFExtractor
from vedic_translator.document_processor.extractors.txt import TXTExtractor

__all__ = [
    "BaseExtractor",
    "compute_file_sha256",
    "validate_source_file",
    "DocumentExtractor",
    "PDFExtractor",
    "EPUBExtractor",
    "DOCXExtractor",
    "TXTExtractor",
]
