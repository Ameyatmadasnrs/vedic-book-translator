# System Architecture Specification

**Project Name**: Vedic Book Translator  
**Architecture Pattern**: Hexagonal Architecture (Ports & Adapters) with Event-Driven Pipeline  
**Target Runtimes**: Python 3.12+ (AsyncIO), Cross-Platform (Windows, Linux, macOS)  
**Document Version**: 1.1.0 (Post-Audit Revision)  
**Status**: Revised Foundation  

---

## 1. Architectural Philosophy & Principles

The Vedic Book Translator is engineered as a modular, loosely-coupled, highly-extensible platform following the **Hexagonal Architecture (Ports and Adapters)** pattern.

### 1.1 Core Architectural Principles
1. **Separation of Concerns**: Core domain entities (Document AST, Translation Units, Terminology Models) are entirely agnostic of third-party frameworks, AI provider SDKs, and storage engines.
2. **Provider & Model Independence**: External LLM services (OpenAI, Anthropic Claude, Google Gemini, Ollama, vLLM, custom models) interact with the core domain strictly through abstract interfaces (`Ports`). **No model names or provider IDs are hardcoded into the translation engine or core models**. Model IDs, temperatures, and routing are strictly runtime configurations.
3. **Independent Stage Model Selection**: The architecture guarantees that each stage of the translation workflow can independently utilize a different AI provider and model:
   - *Translation Stage (Source -> Draft)*: Independently configurable provider and model.
   - *Philosophical Review Stage*: Independently configurable provider and model.
   - *Literary Russian Polish Stage*: Independently configurable provider and model.
   - *Terminology & Diacritics Validation Stage*: Independently configurable provider and model.
4. **Digital-First Ingestion**: Focus Phase 1 strictly on high-fidelity digital text extraction (digital vector PDF, EPUB, DOCX, TXT). Scanned physical document OCR is decoupled into a dedicated subsequent subsystem.
5. **Configurable Orthography Profiles**: Transliteration and orthography rules (e.g., BBT Russian standard vs. Academic Cyrillic) are externalized into interchangeable profiles (`OrthographyProfile`).
6. **Multi-Dimensional Quality Governance**: Automated checks provide diagnostic findings; human editorial approval is the authoritative publishing gate.
7. **Immutability of Ingestion**: Source documents are treated as read-only. Ingestion converts arbitrary documents into a canonical in-memory Abstract Syntax Tree (AST), which is then processed through pipeline stages into new target formats.
8. **Idempotence & Resumability**: Every step in the translation and auditing lifecycle writes atomic checkpoints to a persistent store. If processing is interrupted, the job resumes from the last completed block.

---

## 2. System Decomposition & Subsystem Responsibilities

```
+----------------------------------------------------------------------------------------------------+
│                                    CLI & Orchestration Layer                                       │
│                              (Job Manager, Runner, Progress UI)                                    │
+----------------------------------------------------------------------------------------------------+
           │                                       │                                      │
           ▼                                       ▼                                      ▼
+-----------------------+              +-----------------------+              +-----------------------+
│   Document Processor  │              │   Translation Engine  │              │   Publishing Engine   │
│ (Digital Extractors)  │              │  (4-Stage Multi-LLM)  │              │ (DOCX, EPUB, PDF, MD) │
+-----------------------+              +-----------------------+              +-----------------------+
           │                                       │                                      │
           │                  +--------------------+--------------------+                 │
           │                  │                                         │                 │
           ▼                  ▼                                         ▼                 ▼
+--------------------------------------+                     +--------------------------------------+
│       Domain AST & Core Models       │                     │     Quality Control & Auditing       │
│ (Document, Chapter, Section, Block)  │                     │   (6-Dimension Quality Framework)    │
+--------------------------------------+                     +--------------------------------------+
                              │                                         │
                              ▼                                         ▼
+----------------------------------------------------------------------------------------------------+
│                                    Memory & Storage Subsystem                                      │
│                  (Translation Memory, Configurable Glossaries, Job Checkpoints)                    │
+----------------------------------------------------------------------------------------------------+
```

### 2.1 Subsystem Responsibilities

#### Subsystem 1: Document Processor
- **Primary Function**: Ingest arbitrary digital input files and convert them into a typed, structured **Document AST**.
- **Key Modules**:
  - `extractors/`: Format-specific parsers (`pdf.py`, `epub.py`, `docx.py`, `txt.py`).
  - `segmenter/`: Rule-based and pattern-based semantic splitter that classifies text blocks into Verses (Devanagari/IAST), Synonyms, Translations, Purports, Headings, and Narrative Paragraphs.
  - *Note on OCR*: Scanned document OCR is isolated as a future planned subsystem, not bundled into digital ingestion.

#### Subsystem 2: Translation Engine
- **Primary Function**: Transform segmented source blocks into high-fidelity Russian text across four discrete, specialized stages.
- **Key Modules**:
  - `providers/`: Concrete adapters for OpenAI, Anthropic Claude, Google Gemini, and Local/Open-Source LLMs (vLLM, Ollama) implementing `ITranslationProvider`.
  - `prompts/`: Versioned prompt templates tailored to each stage and textual genre.
  - `pipeline/`: Four sequential transformation stages:
    1. `literal_stage.py`: Morphological deconstruction and lexical mapping.
    2. `philosophical_stage.py`: Gaudiya Vaishnava Siddhanta and commentary alignment.
    3. `literary_stage.py`: Russian stylistic elegance and rhythmic prose refinement.
    4. `terminology_stage.py`: Terminology profile and diacritical harmonization.
  - `context_manager.py`: Injects relevant chapter synopsis, dramatis personae, and preceding narrative into model prompts.

#### Subsystem 3: Quality Control & Auditing System
- **Primary Function**: Continuous verification of translations across the 6 quality dimensions.
- **Key Modules**:
  - `linguistic_auditor.py`: Syntactic dependency and clause mapping diagnostics.
  - `philosophical_auditor.py`: Doctrinal rubric checks against impersonal/Mayavada deviations.
  - `terminology_auditor.py`: Conformance checking against the active `OrthographyProfile` and glossary.
  - `structural_auditor.py`: Deterministic verification of verse completeness, numbering, and element counts.
  - `literary_auditor.py`: Stylistic heuristics (passive voice detection, lexical balance).
  - `human_approval_gate.py`: Workflow management for human editorial sign-off.

#### Subsystem 4: Publishing Engine
- **Primary Function**: Format and render the translated AST into publication-quality distribution documents.
- **Key Modules**:
  - `docx_exporter.py`: Generates Microsoft Word files with dedicated paragraph styles (Verse, Synonyms, Purport, Heading), dynamic TOC, and footnotes.
  - `epub_exporter.py`: Compiles EPUB 3 e-books with semantic HTML5 tags, embedded fonts, and navigation metadata.
  - `pdf_exporter.py`: Compiles print-ready PDFs with dual-script typography (Devanagari + Cyrillic), running headers, and page numbers.
  - `bilingual_exporter.py`: Generates parallel text study layouts.

#### Subsystem 5: Memory & Glossary Subsystem
- **Primary Function**: Manage persistent linguistic assets across sessions and books.
- **Key Modules**:
  - `terminology_db.py`: SQLite-backed dictionary supporting custom glossaries and profile swapping.
  - `translation_memory.py`: Exact and fuzzy-match segment cache storing source hashes, previous translations, and revision histories.
  - `context_store.py`: Persistent storage of entity registers and chapter summaries.

#### Subsystem 6: Orchestrator & Job Lifecycle
- **Primary Function**: Oversee job execution, state persistence, concurrency control, and progress reporting.
- **Key Modules**:
  - `job_manager.py`: Manages job queues, active workers, rate-limiting, and error handling.
  - `checkpoint.py`: Atomic state serialization ensuring complete recovery after process interruption.
  - `runner.py`: CLI entry point (Typer-based) providing commands for translation, status checks, and exports.

---

## 3. Dynamic AI Provider Adapter Specification

To ensure total decoupling and eliminate hardcoded model identifiers, providers implement the following port:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ProviderCompletionRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model_id: str  # DYNAMIC: Configured per stage, never hardcoded
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    extra_params: Dict[str, Any] = {}


class ProviderCompletionResponse(BaseModel):
    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class ITranslationProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Return provider identifier (e.g. 'openai', 'anthropic', 'gemini', 'local')."""
        pass

    @abstractmethod
    async def complete(self, request: ProviderCompletionRequest) -> ProviderCompletionResponse:
        """Execute completion request against external API."""
        pass
```

### Stage-by-Stage Independent Configuration Schema
```yaml
pipeline:
  stages:
    literal_stage:
      provider: "gemini"
      model_id: "${GEMINI_MODEL_ID:-gemini-1.5-pro}"
      temperature: 0.1
    philosophical_stage:
      provider: "anthropic"
      model_id: "${ANTHROPIC_MODEL_ID:-claude-3-5-sonnet-20241022}"
      temperature: 0.2
    literary_stage:
      provider: "openai"
      model_id: "${OPENAI_MODEL_ID:-gpt-4o}"
      temperature: 0.3
    terminology_stage:
      provider: "gemini"
      model_id: "${GEMINI_MODEL_ID:-gemini-1.5-pro}"
      temperature: 0.0
```

---

## 4. Canonical Document AST (Abstract Syntax Tree)

The hierarchical AST built on **Pydantic v2**:

```
Document
└── DocumentMetadata (title, author, source_lang, target_lang, orthography_profile)
└── List[Chapter]
    ├── chapter_index
    ├── title
    ├── summary
    └── List[Section]
        ├── section_index
        ├── verse_range
        └── List[Block]
            ├── id (UUID)
            ├── type (VERSE_DEVANAGARI, VERSE_IAST, SYNONYMS, TRANSLATION, PURPORT, PARAGRAPH, FOOTNOTE)
            ├── source_text (IMMUTABLE source)
            ├── target_text (Current candidate / approved translation)
            ├── state (INGESTED, STAGE_1, STAGE_2, STAGE_3, STAGE_4, QC_VERIFIED, APPROVED)
            ├── history: List[StageAudit] (Full versioned history of every stage output)
            └── audit_result: Optional[AuditResult] (Diagnostic findings across 6 dimensions)
```

---

## 5. Storage & Persistence Architecture

1. **`translations.db` (Translation Memory & Job Checkpoints)**:
   - `jobs`: Tracks overall book translation status, active settings, and completion percentage.
   - `blocks`: Stores every AST block with its source hash, state, and intermediate stage outputs.
   - `translation_memory`: Key-value cache indexing `SHA256(source_text + context_domain)` to approved Russian translation.
2. **`terminology.db` (Vedic & Gaudiya Lexicon)**:
   - Configurable per-book glossaries and active `OrthographyProfile`.
3. **`checkpoints/` (File System Mirror)**:
   - Atomic JSONL checkpoints written per chapter to allow recovery and manual Git auditing.
