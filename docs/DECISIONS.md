# Architecture Decision Records (ADRs)

This document records the architectural and technology choices made for the **Vedic Book Translator** platform, including the context, decision, consequences, and alternatives considered.

---

## ADR-001: Selection of Hexagonal Architecture (Ports & Adapters)

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  The system must process diverse document formats (PDF, EPUB, DOCX, TXT), connect to multiple AI providers (Gemini, Claude, OpenAI, local LLMs), store state in local databases, and export to various publishing targets. Coupling the business logic to any specific provider SDK, file library, or database would lead to fragile, unmaintainable code that breaks when external APIs evolve.
- **Decision**:
  Adopt the **Hexagonal Architecture** (Ports and Adapters) pattern. Core domain models (Document AST, Verse models, Terminology rules) reside at the center and have zero dependencies on external frameworks or drivers. All I/O, AI model interactions, document parsers, and exporters are implemented as concrete Adapters implementing formal abstract Ports (`Protocol` or `ABC`).
- **Consequences**:
  - *Positive*: Easy to add new AI providers, new input/output formats, or switch storage backends without modifying core translation logic.
  - *Positive*: Simplifies unit testing through straightforward mocking of ports.
  - *Negative*: Introduces minor boilerplate with interface definitions and data mapping layers.
- **Alternatives Considered**:
  - *Monolithic Scripting*: Rejected due to high risk of tight coupling and low testability.
  - *Layered Architecture*: Rejected because domain logic frequently ends up dependent on data access layers.

---

## ADR-002: Python 3.12+ as Primary Implementation Language

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  The platform requires rich document parsing (PDF, EPUB, DOCX), OCR capabilities, advanced NLP for Sanskrit transliteration, morphological analysis for Russian declensions, and high-performance asynchronous orchestration of AI APIs.
- **Decision**:
  Standardize on **Python 3.12+** using `asyncio` for concurrent pipeline operations.
- **Consequences**:
  - *Positive*: Unrivaled ecosystem for document parsing (`PyMuPDF`, `python-docx`, `EbookLib`), Sanskrit NLP (`indic-transliteration`), Russian morphology (`pymorphy3`), and official AI SDKs (`google-genai`, `anthropic`, `openai`).
  - *Positive*: Python 3.12 provides significant performance improvements (specialized adaptive interpreter, faster async event loops).
  - *Negative*: Slower raw CPU execution compared to Rust/Go, but this is negligible since 95% of runtime is I/O-bound (LLM API calls and disk operations).
- **Alternatives Considered**:
  - *TypeScript/Node.js*: Strong ecosystem, but significantly weaker library support for Sanskrit transliteration engines, complex PDF parsing, and Russian morphological analysis.
  - *Rust*: High performance and safety, but lacks specialized mature libraries for Sanskrit/Russian computational linguistics and rapid prompt iteration.

---

## ADR-003: 4-Stage Multi-LLM Pipeline vs. Single-Shot Prompting

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Translating sacred Vedic texts into Russian requires simultaneous syntactic deconstruction, Gaudiya theological alignment, Russian literary elegance, and strict terminology/diacritic compliance. Attempting to achieve all four goals in a single LLM prompt results in severe compromises: hallucinated verses, flattened philosophy, dropped diacritics, or wooden phrasing.
- **Decision**:
  Decompose the translation process into four discrete, sequential, auditable stages:
  1. **Stage 1 (Literal)**: Grammatical and morphological deconstruction.
  2. **Stage 2 (Philosophical)**: Gaudiya Vaishnava Siddhanta and commentary alignment.
  3. **Stage 3 (Literary)**: High-register Russian prose styling.
  4. **Stage 4 (Terminology)**: BBT Russian orthography and diacritic harmonization.
- **Consequences**:
  - *Positive*: Each stage has a single, verifiable responsibility with measurable quality metrics.
  - *Positive*: Allows model routing (e.g., using Gemini for high-context extraction, Claude for deep theological analysis, and GPT-4o for Russian stylistic polish).
  - *Negative*: Increases token consumption and latency per block compared to a single prompt. This is mitigated by Translation Memory caching and concurrent block execution.
- **Alternatives Considered**:
  - *Single Large Prompt*: High rate of subtle theological errors and dropped diacritics.
  - *Two-Stage (Translate -> Polish)*: Failed to separate deep theological commentary auditing from superficial Russian prose editing.

---

## ADR-004: Native Provider SDKs with Abstract Port over LangChain/LlamaIndex

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Popular orchestration frameworks like LangChain and LlamaIndex provide pre-built chains and abstractions. However, they frequently introduce dependency bloat, breaking changes between minor versions, opaque abstractions, and latency overhead.
- **Decision**:
  Implement lightweight, native adapters directly wrapping official SDKs (`google-genai`, `anthropic`, `openai`) behind a lean domain interface (`ITranslationProvider`).
- **Consequences**:
  - *Positive*: Zero vendor lock-in; exact control over system prompts, temperature, token limits, and error handling.
  - *Positive*: Minimal third-party dependencies, leading to high stability and rapid cold-start times.
  - *Negative*: Requires implementing custom retry logic and token-bucket rate limiting (achieved cleanly with `tenacity` and `asyncio`).
- **Alternatives Considered**:
  - *LangChain / LangGraph*: Rejected due to high dependency churn, excessive abstractions, and frequent breaking changes.
  - *LlamaIndex*: Excellent for retrieval, but unnecessarily complex for a sequential multi-stage translation pipeline.

---

## ADR-005: Canonical Strongly-Typed AST Representation (Pydantic v2)

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Documents arrive in varied formats (PDF, EPUB, DOCX, TXT) with heterogeneous internal structures. If translators and publishers operate on raw text or ad-hoc dictionaries, structural features (such as Sanskrit meter, word-for-word synonyms, footnotes, and headings) are easily corrupted or lost.
- **Decision**:
  Define a canonical hierarchical **Document Abstract Syntax Tree (AST)** using `pydantic.BaseModel` v2. The hierarchy is `Document -> Chapter -> Section -> Block`. Each block possesses a strongly-typed `BlockType` (`VERSE_DEVANAGARI`, `VERSE_IAST`, `SYNONYMS`, `TRANSLATION`, `PURPORT`, `PARAGRAPH`, etc.) and maintains its full transformation history.
- **Consequences**:
  - *Positive*: High-performance validation and serialization.
  - *Positive*: Subsystems operate against an unambiguous, type-safe data model.
  - *Negative*: Ingestion extractors must parse document structure accurately into AST nodes.
- **Alternatives Considered**:
  - *Raw Markdown / Pandoc AST*: Inadequate for expressing specialized Vedic verse units (Devanagari + IAST + Synonyms + Translation + Purport).
  - *Plain Python Dictionaries*: Lacks static type checking and automated validation.

---

## ADR-006: Local SQLite Persistence for Translation Memory & Checkpoints

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Vedic book translation involves long-running jobs that must be resumable. Furthermore, identical verses, synonyms, and prayers appear repeatedly across scriptures. We need a fast, zero-configuration, cross-platform persistence engine for translation memory and checkpoints.
- **Decision**:
  Use **SQLite 3** (via `sqlite-utils` and standard library `sqlite3`) with WAL (Write-Ahead Logging) mode enabled, complemented by atomic JSONL file mirrors for chapter-level checkpoints.
- **Consequences**:
  - *Positive*: Zero external database server requirements (runs out of the box on any workstation).
  - *Positive*: ACID-compliant transactions ensure state is never corrupted if a job is killed.
  - *Positive*: High read throughput for terminology queries and exact hash lookups.
  - *Negative*: Not designed for high-concurrency multi-node distributed writing (sufficient for our single-workstation/server CLI architecture).
- **Alternatives Considered**:
  - *PostgreSQL*: Heavyweight prerequisite requiring server setup and maintenance.
  - *Pure JSON Files*: Prone to race conditions and file corruption on mid-write crashes; inefficient for searching large translation memories.

---

## ADR-007: Non-Destructive Ingestion & Preserving Original Verse Elements

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Translating a sacred text must never alter or destroy user files. Furthermore, readers and scholars require verifying the Russian translation against the original Sanskrit meter and Roman transliteration.
- **Decision**:
  Source documents are treated as strictly immutable (read-only). Output files are written to dedicated output directories. In the Document AST, original Devanagari verses, IAST transliterations, and English sources are permanently preserved alongside the target Russian text, enabling bilingual parallel editions.
- **Consequences**:
  - *Positive*: Guaranteed safety of user data; zero data loss risk.
  - *Positive*: Enables multi-language study and parallel publication layouts.
  - *Negative*: Output files contain larger payload sizes due to dual-language retention.

---

## ADR-008: Adoption of BBT Russian Orthography as Primary Standard

- **Status**: Accepted
- **Date**: 2026-11-22
- **Context**:
  Over five decades, the Bhaktivedanta Book Trust (BBT) has established the definitive standard for translating Vedic and Vaishnava terminology into Russian. Russian readers expect familiar terms (*Кришна*, *Чайтанья*, *Вриндаван*, *бхакти*, *гуру*), while academic scholars often use alternative transliterations (e.g., *Кршна*, *Чаитанйа*, *Врндавана*).
- **Decision**:
  Adopt the **BBT Russian Transliteration and Orthographic Standard** as the default system configuration, while supporting an optional configuration toggle for pure academic/scholarly Russian transliteration.
- **Consequences**:
  - *Positive*: High acceptance and immediate familiarity among the primary readership and publishing houses.
  - *Positive*: Clear, unambiguous transliteration guidelines documented in `glossaries/`.
  - *Negative*: Requires maintaining mapping tables between standard BBT Cyrillic and international academic IAST.
