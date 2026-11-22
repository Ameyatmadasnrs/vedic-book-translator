# Development Roadmap

**Project Name**: Vedic Book Translator  
**Delivery Model**: Phased Milestones with Strict Acceptance Gates  
**Current Phase**: Phase 0 (Initialization, Audit & Corrective Baseline)  
**Document Version**: 1.1.0 (Post-Audit Revision)  

---

## 1. Roadmap Overview & Timeline

```
+-------------------------------------------------------------------------------------------------------+
│  Phase 0: Initialization, Architectural Audit & Baseline (CURRENT)                                    │
│  - Environment inspection & documentation suite                                                       │
│  - Corrective audit (decoupling model IDs, 6-dimension quality framework, digital-first scope)       │
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 1: Digital Document Ingestion & Canonical Document AST                                         │
│  - Digital Parsers (Digital PDF, EPUB, DOCX, TXT)                                                     │
│  - Semantic Verse & Commentary Segmenter (Devanagari, IAST, Anvaya, Anuvada, Tatparya)                │
│  - Canonical Document AST Validation & Golden Ingestion Tests                                         │
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 2: Translation Memory, Configurable Glossaries & Orthography Profiles                          │
│  - SQLite Storage Engine (ACID transactions, WAL mode)                                                │
│  - Pluggable Orthography Profiles (BBT Russian Profile, Academic Cyrillic Profile)                    │
│  - Custom Lexicon Loader & Sanskrit-Russian Morphological Declension Integration                     │
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 3: Multi-Provider Adapters & 4-Stage Translation Pipeline                                      │
│  - Independent Provider Adapters: OpenAI, Anthropic Claude, Google Gemini, Local LLMs                 │
│  - Dynamic Stage Configuration: Independent model ID & parameter selection per stage                  │
│  - Stage 1 (Literal) -> Stage 2 (Philosophical) -> Stage 3 (Literary) -> Stage 4 (Terminology)        │
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 4: Multi-Dimensional Quality Control & Human Editorial Gate                                    │
│  - Automated Diagnostic Audits (Linguistic, Philosophical, Terminology, Structural, Literary)        │
│  - Human Editorial Sign-Off Workflow & Anomaly Routing                                                │
│  - Golden Verse Reference Test Suite (Bhagavad-gita 2.13, Srimad-Bhagavatam 1.1.1)                   │
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 5: Publishing Engine, Multi-Format Exporters & Scanned OCR Subsystem                           │
│  - Publication-Grade DOCX Exporter (Styles, Footnotes, Parallel Layouts)                              │
│  - Validated EPUB 3 Exporter with Font Embedding                                                      │
│  - Typeset PDF Exporter (Dual-Script Typography)                                                      │
│  - Planned Scanned OCR Subsystem (Advanced Devanagari Ligature Pre-processing & Vision-LLM Assistance)│
+-------------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+-------------------------------------------------------------------------------------------------------+
│  Phase 6: CLI Runner, Job Orchestration & Production Hardening                                        │
│  - Atomic Checkpointing & Resumable Job State Machine                                                 │
│  - Rich Terminal Dashboard (Progress, Cost Estimates, Audit Findings)                                 │
│  - Full Multi-Chapter Book End-to-End Stress Testing                                                  │
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Phase Breakdown & Acceptance Gates

### Phase 0: Project Initialization, Corrective Audit & Baseline (Current)
- **Objective**: Establish foundational documentation, verify environment, decouple model configurations, and set quality standards.
- **Deliverables**:
  - Full documentation suite under `docs/`
  - Corrective audit addressing test failures, hardcoded model decoupling, and quality architecture.
- **Acceptance Gate**: Explicit client review and approval of the Corrective Audit Report.

---

### Phase 1: Digital Document Ingestion & Canonical Document AST
- **Objective**: Build robust, non-destructive digital document ingestion that parses structured Vedic texts into a strongly-typed Document AST.
- **Key Deliverables**:
  1. `DocumentExtractor` abstract port and concrete digital extractors:
     - `PDFExtractor` (PyMuPDF) supporting digital vector text, bookmarks, and font extraction.
     - `EPUBExtractor` (EbookLib + BeautifulSoup4) retaining chapter hierarchy.
     - `DOCXExtractor` (python-docx) extracting styled headings, italics, and footnotes.
     - `TXTExtractor` with regex pattern recognition for markdown/plain text.
  2. `SemanticSegmenter`: Pattern-based classifier that identifies:
     - Devanagari verse blocks (*Mūla-śloka*).
     - IAST transliteration blocks.
     - Word-for-word synonyms (*Anvaya*).
     - Literary translations (*Anuvāda*).
     - Commentaries/purports (*Tātparya*).
     - Headings and prose narrative paragraphs.
- **Acceptance Gate**:
  - Ingestion of test sample (*Bhagavad-gītā* Chapter 2) produces a 100% accurate Document AST with zero dropped verses, zero corrupted footnotes, and exact block classifications.
  - All Phase 1 tests pass in an isolated virtual environment.

---

### Phase 2: Translation Memory, Configurable Glossaries & Orthography Profiles
- **Objective**: Implement zero-dependency local storage for translation memory, terminology lookup, and interchangeable orthographic profiles.
- **Key Deliverables**:
  1. `SQLiteTranslationMemory`:
     - SHA-256 hash indexing of source segments.
     - Exact match and fuzzy match retrieval.
     - Full provenance tracking (model used, stage history, human approval status).
  2. `OrthographyProfileManager`:
     - Pluggable profile system: BBT Russian Profile (default) and Academic Cyrillic Profile.
     - Dynamic custom glossary loader for user-provided dictionaries.
     - Sanskrit-Russian morphological declension integration.
- **Acceptance Gate**:
  - Sub-millisecond lookup latency for terminology queries.
  - Test suite validating declension cases for all terms in the seed dictionary.

---

### Phase 3: Multi-Provider Adapters & 4-Stage Translation Pipeline
- **Objective**: Implement independent, pluggable AI provider adapters with dynamic model ID configuration.
- **Key Deliverables**:
  1. `ITranslationProvider` abstract port and independent concrete adapters:
     - `OpenAIProvider` (supporting `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`, etc.).
     - `AnthropicProvider` (supporting `claude-3-5-sonnet`, `claude-3-5-haiku`, etc.).
     - `GeminiProvider` (supporting `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`, etc.).
     - `LocalProvider` (OpenAI-compatible endpoints: vLLM, Ollama, LM Studio).
  2. Fully independent stage model selection: each stage specifies its own provider and dynamic model ID.
  3. Resilient API layer with token-bucket rate limiting and exponential backoff retry.
- **Acceptance Gate**:
  - Verification with recorded mock fixtures proving seamless provider switching and zero hardcoded model dependencies.

---

### Phase 4: Multi-Dimensional Quality Control & Human Editorial Gate
- **Objective**: Implement automated diagnostic checks across the 6 quality dimensions and provide human editorial workflows.
- **Key Deliverables**:
  1. Automated diagnostic auditors:
     - Linguistic & Syntactic Auditor.
     - Philosophical & Doctrinal Auditor (Gaudiya Siddhanta contrast rubrics).
     - Terminology & Orthography Profile Auditor.
     - Structural Completeness Auditor (100% invariant check).
     - Literary Register Auditor (Russian stylistic balance).
  2. Human-in-the-Loop Editorial Gate:
     - Flagging low-confidence or doctrine-sensitive blocks.
     - Capturing human corrections directly back into Translation Memory.
- **Acceptance Gate**:
  - Verification engine detects 100% of synthetic errors (injected Mayavada phrasing, dropped verses, broken diacritics).

---

### Phase 5: Publishing Engine, Multi-Format Exporters & Scanned OCR Subsystem
- **Objective**: Transform verified AST into publication-ready files, and deliver the planned advanced OCR subsystem for scanned books.
- **Key Deliverables**:
  1. Exporters:
     - `DOCXExporter`: Publication styles, running headers, footnotes, verse callouts.
     - `EPUBExporter`: EPUB 3 compliant with embedded Devanagari and Cyrillic fonts.
     - `PDFExporter`: Typeset dual-script layouts.
  2. Scanned OCR Subsystem:
     - Advanced image pre-processing (binarization, skew correction, noise removal).
     - Sanskrit conjunct ligature normalization.
     - Vision-LLM assisted transcription review for ancient manuscripts.
- **Acceptance Gate**:
  - Exported DOCX and EPUB pass strict third-party validator checks (`epubcheck`).

---

### Phase 6: CLI Runner, Job Orchestration & Production Hardening
- **Objective**: Integrate all components into a robust, resumable CLI tool.
- **Key Deliverables**:
  1. `JobManager`: Background worker pool, concurrency limits, and atomic SQLite/JSONL checkpoints.
  2. Interactive `Typer` CLI with rich progress dashboards.
  3. Multi-chapter end-to-end translation testing.
- **Acceptance Gate**:
  - Abrupt process interruption (kill -9) resumes cleanly without missing or duplicating text.
