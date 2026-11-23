# AGENTS.md — AI Agent Operating Guidelines & Contributor Handbook

Welcome to the **Vedic Book Translator** repository. This document defines the engineering standards, architectural guardrails, domain constraints, and operational procedures for all AI agents and human engineers contributing to this codebase.

---

## 1. Prime Directives (Non-Negotiable)

Every agent executing tasks in this repository must uphold the following rules without exception:

1. **Non-Destructive Ingestion**: Never overwrite or delete user source files. The ingestion process must always be read-only. Intermediate artifacts and outputs must be written to designated output directories (`data/output/`, `data/checkpoints/`).
2. **Credential Safety**: Never hardcode API keys, passwords, or secrets. All credentials must be read from environment variables or a local `.env` file (loaded via `pydantic-settings`).
3. **No Speculative Implementation**: Do not implement features, sub-modules, or integrations that have not been explicitly approved in the architecture and roadmap.
4. **No Fabricated Capabilities**: Never assume external API features or invent endpoints. Consult official SDK documentation for Google Gemini, Anthropic Claude, OpenAI, and local runners.
5. **Dependency Discipline**: Do not add third-party libraries without documenting their purpose, license, and architectural justification in `docs/DECISIONS.md`.
6. **Synchronized Documentation**: Any architectural modification, new configuration flag, or schema change must immediately be reflected across `docs/`, `CHANGELOG.md`, and inline type annotations.
7. **Test-Driven Delivery**: Never mark a feature complete without corresponding automated unit, integration, and golden tests. Maintain minimum 85% test coverage.
8. **Theological & Philological Fidelity**: Vedic, Sanskrit, and Gaudiya Vaishnava texts must not be flattened or subjected to impersonal/Mayavada interpretations. Preserve verse structure, word-for-word synonyms (*anvaya*), and diacritical marks.

---

## 2. Specialized Agent Roles

When collaborating or delegating within this repository, agents must adopt one of the following specialized roles:

### A. Lead Architect Agent
- **Responsibilities**: System integrity, schema design (Pydantic models), interface definitions (ABCs / Protocols), module boundaries, architectural decision records (`docs/DECISIONS.md`), and PR reviews.
- **Tools**: Type checker (`mypy`), linting (`ruff`), architectural diagrams, interface validators.

### B. Document Processing Agent
- **Responsibilities**: Ingestion parsers (PDF, EPUB, DOCX, TXT), OCR pipelines (Tesseract/PyMuPDF), document cleanup, structural and semantic segmentation (chapter detection, verse/purport identification), and Document AST generation.
- **Guiding Principle**: Preserve original layout metadata, footnote links, and verse numbers with 100% fidelity.

### C. Translation & Linguistics Agent
- **Responsibilities**: LLM prompt engineering, multi-stage translation pipelines, Sanskrit morphological processing, transliteration conversions (IAST, Devanagari, Cyrillic), translation memory management, and glossary injection.
- **Guiding Principle**: Maintain Gaudiya Vaishnava theological precision, BBT Russian transliteration conventions, and high literary Russian cadence.

### D. Quality Assurance Agent
- **Responsibilities**: Automated QA pipelines, hallucination detection, omission detection, diacritics completeness checks, terminology auditing, benchmark evaluations, and test suite maintenance.
- **Guiding Principle**: Reject any translation segment where terms violate the approved glossary or where verses/paragraphs are omitted.

### E. Publishing & Typography Agent
- **Responsibilities**: Exporters (DOCX, EPUB, PDF), typesetting rules, Devanagari font embedding, Cyrillic diacritic rendering, running headers, bilingual parallel verse formatting, and footnote placement.
- **Guiding Principle**: Deliver publication-ready, beautifully typeset books ready for professional printing or digital distribution.

---

## 3. Standard Operating Procedure for Task Execution

Before writing or modifying any code, an agent must execute the following 5-phase loop:

```
[1. Context Ingestion] 
       ↓ (Read docs, verify existing interfaces and dependencies)
[2. Design & Impact Analysis]
       ↓ (Check ADRs, assess breaking changes, plan test cases)
[3. Implementation]
       ↓ (Clean, strictly-typed code complying with Hexagonal Architecture)
[4. Verification & Testing]
       ↓ (Run ruff, mypy, pytest, and golden fixture checks)
[5. Documentation & Checkpointing]
       ↓ (Update CHANGELOG.md, relevant docs, commit with Conventional Commits)
```

---

## 4. Coding & Architectural Standards

- **Python Version**: 3.12+
- **Typing**: Strict type annotations on all function signatures, classes, and attributes. No bare `Any` without explicit justification.
- **Data Validation**: Use `pydantic.BaseModel` (v2) for all data transfer objects, AST nodes, and API payloads.
- **Architecture**: Hexagonal (Ports & Adapters). Business logic in domain services must never depend directly on external APIs or database drivers; use abstract interfaces (`Protocol` or `ABC`).
- **Asynchrony**: All I/O-bound operations (LLM calls, disk reads/writes, external HTTP requests) must provide asynchronous interfaces using Python `asyncio`.
- **Error Handling**: Use custom domain exceptions derived from `vedic_translator.core.exceptions.VedicTranslatorError`. Never silently catch or pass unhandled exceptions.

---

## 5. Git Commit Protocol

All agents must commit milestones following the **Conventional Commits** specification:

- `feat(scope)`: A new feature (e.g., `feat(ocr): add tesseract layout analysis for scanned sanskrit`)
- `fix(scope)`: A bug fix (e.g., `fix(parser): resolve dropped footnotes in epub extraction`)
- `docs(scope)`: Documentation updates only
- `refactor(scope)`: Code changes that neither fix a bug nor add a feature
- `test(scope)`: Adding missing tests or correcting existing tests
- `chore(scope)`: Maintenance, dependencies, or configuration changes

---

## 6. Pre-Commit Checklist for Agents

Before reporting a task as complete:
- [ ] Are all types annotated and passing `mypy --strict`?
- [ ] Does the code pass `ruff check .` and `ruff format --check .`?
- [ ] Are new and existing tests passing via `pytest`?
- [ ] Are no API keys or credentials exposed in code or config files?
- [ ] Is original source text preserved without mutation?
- [ ] Was `CHANGELOG.md` updated with human-readable notes?
- [ ] If architectural assumptions changed, was an ADR added to `docs/DECISIONS.md`?

---

## 7. Workspace Hygiene & Execution Isolation

1. **Working Directory Integrity**: Always execute commands, pytest sessions, formatters, and scripts from the project root (`C:\Users\Ameya\Desktop\vedic-book-translator`). Never invoke commands from the parent desktop directory.
2. **Cache Isolation**: Ensure `.pytest_cache/`, `.coverage`, `.mypy_cache/`, and `.ruff_cache/` are stored strictly within the project repository and are excluded by `.gitignore`. Never allow cache files to be emitted onto the Windows Desktop.
3. **External File Safety**: Never delete, move, or modify files outside the project root without explicit user instruction.
