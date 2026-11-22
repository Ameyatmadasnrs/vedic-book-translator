# Changelog

All notable changes to the **Vedic Book Translator** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Phase 1.2: Semantic Verse & Commentary Segmentation (Devanagari, IAST, Anvaya, Anuvāda, Tātparya).
- Phase 2: Translation Memory & Terminology Store with BBT Russian orthography.
- Phase 3: AI Provider Adapters (Gemini, Claude, OpenAI) & 4-Stage Translation Pipeline.
- Phase 4: Automated Quality Control & Multi-Dimensional Auditing.
- Phase 5: Publishing Engine (DOCX, EPUB, PDF exporters) & Scanned OCR Subsystem.
- Phase 6: CLI Runner & Job State Orchestrator.

---

## [0.1.1-alpha.0] - 2026-11-22

### Added
- **Digital Document Extraction (Phase 1.1)**:
  - `BaseExtractor`: Formal abstract port for format-specific extractors with SHA-256 pre/post integrity hashing.
  - `PDFExtractor`: High-performance digital vector PDF extraction using PyMuPDF, preserving reading order, TOC bookmark chapters, and page metadata.
  - `EPUBExtractor`: EPUB 2 and EPUB 3 extractor using EbookLib and BeautifulSoup4, traversing spine items to guarantee reading order, extracting Dublin Core metadata and HTML headings.
  - `DOCXExtractor`: Word document extractor using python-docx, preserving heading levels (Heading 1-3, Title), paragraphs, tables, and document properties.
  - `TXTExtractor`: Plain text and Markdown extractor supporting UTF-8 and fallback encodings, regex-based chapter/section detection, and Unicode preservation.
  - `DocumentExtractor`: Unified facade coordinating format dispatch, validation, and automated non-destructive file immutability verification.
- **Test Suite Expansion**:
  - Added unit test suites for `TXTExtractor`, `DOCXExtractor`, `EPUBExtractor`, and `PDFExtractor`.
  - Added integration test suite verifying multi-format routing, corrupted file rejection, unsupported format detection, and source file immutability (26 tests total, 100% pass rate).

---

## [0.1.0-alpha.0] - 2026-11-22

### Added
- **Project Foundation**: Initialized Git repository, project directory structure, and environment templates (`.gitignore`, `.env.example`).
- **Dependency Specification**: Created `pyproject.toml` targeting Python 3.12+ with Pydantic v2, PyMuPDF, python-docx, EbookLib, native AI provider SDKs, and linting/testing configurations.
- **Agent Operating Standards**: Published `AGENTS.md` specifying prime directives, specialized agent roles, Git commit conventions, and pre-commit verification checklists.
- **Product Requirements Specification**: Published `docs/PRODUCT_REQUIREMENTS.md` covering functional and non-functional requirements, personas, structural text components, and edge cases.
- **System Architecture**: Published `docs/SYSTEM_ARCHITECTURE.md` defining the Hexagonal Architecture, core subsystems (Document Processor, Translation Engine, QC System, Publishing Engine), AST document model, and data flow.
- **Development Roadmap**: Published `docs/DEVELOPMENT_ROADMAP.md` establishing a 7-phase delivery plan from initialization to production hardening.
- **Translation Methodology**: Published `docs/TRANSLATION_METHODOLOGY.md` detailing the 4-stage translation pipeline (literal, theological, literary, terminology) and rules for Vedic/Sanskrit verse structures.
- **Quality & Engineering Standards**: Published `docs/QUALITY_STANDARDS.md` establishing coding guidelines, test coverage thresholds, and translation evaluation metrics.
- **Architecture Decision Records**: Published `docs/DECISIONS.md` containing ADR-001 through ADR-008 documenting core technology choices and architectural rationale.
- **Curated Glossaries & Configs**: Created foundational glossary structures and YAML configuration files for Gaudiya Vaishnava terminology, IAST diacritics mapping, and BBT Russian transliteration rules.
