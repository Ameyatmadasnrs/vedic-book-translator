"""Abstract base class and utilities for digital document extractors."""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from vedic_translator.core.exceptions import (
    CorruptedDocumentError,
    IngestionError,
)
from vedic_translator.core.models import Document, DocumentMetadata


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file without modifying it (read-only binary mode)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_source_file(file_path: Path) -> None:
    """Verify that the source file exists, is a regular file, and is non-empty."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source document not found: {file_path}")
    if not file_path.is_file():
        raise IngestionError(f"Target path is not a regular file: {file_path}")
    if file_path.stat().st_size == 0:
        raise CorruptedDocumentError(f"Document is empty (0 bytes): {file_path}")


class BaseExtractor(ABC):
    """Abstract base class for all format-specific digital document extractors.

    All implementations must treat the source document as strictly read-only.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Set of supported file extensions (lowercase, e.g. {'.txt', '.md'})."""
        pass

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the given file path."""
        return file_path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def extract(self, file_path: Path) -> Document:
        """Extract a digital document into a canonical Document AST.

        Args:
            file_path: Absolute path to the source document.

        Returns:
            Document: The canonical Document AST representation.

        Raises:
            FileNotFoundError: If the source file does not exist.
            CorruptedDocumentError: If the file is unreadable or malformed.
            UnsupportedFormatError: If the file format is not supported.
        """
        pass

    def _build_initial_metadata(
        self, file_path: Path, title: str | None = None
    ) -> DocumentMetadata:
        """Construct standard initial metadata for a document."""
        file_hash = compute_file_sha256(file_path)
        doc_title = title if title and title.strip() else file_path.stem
        return DocumentMetadata(
            title=doc_title,
            original_file_name=file_path.name,
            original_file_hash=file_hash,
            custom_fields={"file_size_bytes": file_path.stat().st_size},
        )
