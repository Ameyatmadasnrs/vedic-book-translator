"""Unified document extractor factory and dispatcher."""

from pathlib import Path

from loguru import logger

from vedic_translator.core.exceptions import (
    IngestionError,
    UnsupportedFormatError,
)
from vedic_translator.core.models import Document
from vedic_translator.document_processor.extractors.base import (
    BaseExtractor,
    compute_file_sha256,
    validate_source_file,
)
from vedic_translator.document_processor.extractors.docx import DOCXExtractor
from vedic_translator.document_processor.extractors.epub import EPUBExtractor
from vedic_translator.document_processor.extractors.pdf import PDFExtractor
from vedic_translator.document_processor.extractors.txt import TXTExtractor


class DocumentExtractor:
    """Unified entry point for digital document extraction.

    Coordinates format-specific extractors for PDF, EPUB, DOCX, and TXT.
    Guarantees that original source files remain completely untouched.
    """

    def __init__(self, extractors: list[BaseExtractor] | None = None) -> None:
        if extractors is not None:
            self._extractors = extractors
        else:
            self._extractors = [
                PDFExtractor(),
                EPUBExtractor(),
                DOCXExtractor(),
                TXTExtractor(),
            ]

    def register_extractor(self, extractor: BaseExtractor) -> None:
        """Register an additional format extractor."""
        self._extractors.insert(0, extractor)

    def get_extractor_for(self, file_path: Path) -> BaseExtractor:
        """Find the matching extractor for a given file path."""
        for ext in self._extractors:
            if ext.supports(file_path):
                return ext
        raise UnsupportedFormatError(
            f"Unsupported document format '{file_path.suffix}' for file: {file_path.name}"
        )

    def extract(self, file_path: str | Path) -> Document:
        """Extract a digital document into a canonical Document AST.

        Args:
            file_path: Path to the target document (PDF, EPUB, DOCX, or TXT).

        Returns:
            Document: Validated Document AST.

        Raises:
            FileNotFoundError: If the document does not exist.
            UnsupportedFormatError: If the file format is not supported.
            CorruptedDocumentError: If the document cannot be parsed or is corrupted.
        """
        path = Path(file_path).resolve()
        validate_source_file(path)

        extractor = self.get_extractor_for(path)

        # Record file hash prior to extraction to guarantee immutability
        initial_hash = compute_file_sha256(path)

        logger.info(f"Extracting document with {extractor.__class__.__name__}: {path.name}")
        document = extractor.extract(path)

        # Verification: Assert source document was not modified
        post_hash = compute_file_sha256(path)
        if initial_hash != post_hash:
            raise IngestionError(
                f"FATAL: Source file mutation detected! File hash changed during extraction: {path.name}"
            )

        logger.success(
            f"Successfully extracted '{document.metadata.title}' ({document.total_blocks()} blocks) "
            f"from {path.name} [Non-destructive verification passed]"
        )
        return document
