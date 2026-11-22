# Changelog

All notable changes to the **Vedic Book Translator** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Phase 1: Core Document Ingestion & AST Modeling (PDF, DOCX, EPUB, TXT).
- Phase 2: Translation Memory & Terminology Store with BBT Russian orthography.
- Phase 3: AI Provider Adapters (Gemini, Claude, OpenAI) & 4-Stage Translation Pipeline.
- Phase 4: Automated Quality Control & Diacritics Auditor.
- Phase 5: Publishing Engine (DOCX, EPUB, PDF exporters).
- Phase 6: CLI Runner & Job State Orchestrator.

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
