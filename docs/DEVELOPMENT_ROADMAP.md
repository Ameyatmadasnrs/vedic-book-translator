# Development Roadmap

**Project Name**: Vedic Book Translator  
**Delivery Model**: Phased Milestones with Strict Acceptance Gates  
**Current Phase**: Phase 0 (Initialization & Architectural Foundation)  
**Document Version**: 1.0.0  

---

## 1. Roadmap Overview & Timeline

```
+-------------------------------------------------------------------------------------------------------+
|  Phase 0: Initialization & Architecture (COMPLETED IN CURRENT STEP)                                   |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 1: Ingestion, OCR & Canonical Document AST                                                     |
|  - Parsers (PDF, EPUB, DOCX, TXT)                                                                     |
|  - Semantic Verse & Commentary Segmenter                                                              |
|  - OCR Engine for Scanned Texts                                                                       |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 2: Translation Memory & Terminology Store                                                      |
|  - SQLite Storage Engine                                                                              |
|  - Gaudiya Vaishnava Lexicon & BBT Russian Rules                                                      |
|  - Sanskrit Diacritics Mapping & Declension Rules                                                     |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 3: Multi-Provider Adapters & 4-Stage Translation Pipeline                                      |
|  - Adapters: Gemini, Claude, OpenAI, Local LLM                                                        |
|  - Stage 1: Literal Deconstruction                                                                    |
|  - Stage 2: Theological & Commentary Alignment                                                        |
|  - Stage 3: Literary Russian Prose Styling                                                            |
|  - Stage 4: Terminology & Diacritic Harmonization                                                     |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 4: Automated Quality Control & Auditing Engine                                                 |
|  - Terminology Compliance & Mayavada Leakage Auditor                                                  |
|  - Diacritics Completeness Auditor                                                                    |
|  - Verse Numbering & Omission Verifier                                                                |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 5: Publishing Engine & Multi-Format Exporters                                                  |
|  - Publication-Grade DOCX Exporter (Styles, Footnotes)                                                |
|  - Validated EPUB 3 Exporter with Font Embedding                                                      |
|  - Typeset PDF Exporter (Dual-Script Typography)                                                      |
|  - Parallel Bilingual Layout Generator                                                                |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|  Phase 6: CLI Runner, Job Orchestration & Production Hardening                                        |
|  - Atomic Checkpointing & Resume Lifecycle                                                            |
|  - Rich CLI Progress Dashboard                                                                        |
|  - Full Book E2E Golden Verification                                                                  |
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Phase Breakdown & Acceptance Gates

### Phase 0: Project Initialization & Architectural Foundation (Completed)
- **Objective**: Establish development standards, dependency manifests, repository layout, and foundational specifications.
- **Deliverables**:
  - `README.md`, `AGENTS.md`, `CHANGELOG.md`
  - `.gitignore`, `.env.example`, `pyproject.toml`
  - Comprehensive documentation suite under `docs/`
  - Directory skeleton and module structures
- **Acceptance Gate**: Architecture approved by project leadership.

---

### Phase 1: Ingestion, OCR & Canonical Document AST
- **Objective**: Build robust, non-destructive document ingestion capable of extracting complex structured Vedic texts into a strongly-typed Document AST.
- **Key Deliverables**:
  1. `DocumentExtractor` base interface and format adapters:
     - `PDFExtractor` (PyMuPDF) supporting digital text, bookmarks, and font extraction.
     - `EPUBExtractor` (EbookLib + BeautifulSoup4) retaining chapter hierarchy.
     - `DOCXExtractor` (python-docx) extracting styled headings, italics, and footnotes.
     - `TXTExtractor` with regex pattern recognition for markdown/plain text.
  2. `OCREngine` (pytesseract) with image pre-processing for Sanskrit (Devanagari) and Russian/English scanned books.
  3. `SemanticSegmenter`: Rule-based and pattern-based classifier that detects:
     - Devanagari verse blocks (*Mūla-śloka*).
     - IAST transliteration blocks.
     - Word-for-word synonyms (*Anvaya*).
     - Literary translations (*Anuvāda*).
     - Commentaries/purports (*Tātparya*).
     - Prose chapters, headings, and footnotes.
- **Acceptance Gate**:
  - Ingestion of test sample (Bhagavad-gita Chapter 2) creates 100% accurate AST with zero dropped verses and correct block classifications.
  - 100% passing unit tests for each parser.

---

### Phase 2: Translation Memory & Terminology Store
- **Objective**: Implement zero-dependency local storage for translation memory, terminology lookup, and Russian orthographic rules.
- **Key Deliverables**:
  1. `SQLiteTranslationMemory`:
     - SHA-256 hash indexing of source segments.
     - Exact match and fuzzy match retrieval.
     - Provenance tracking (AI model, date, human approval status).
  2. `TerminologyDatabase`:
     - Comprehensive Gaudiya Vaishnava lexicon (seeded with 500+ fundamental theological terms).
     - Russian BBT orthography mapping table (e.g., *Caitanya* → Чайтанья, *Kṛṣṇa* → Кришна).
     - Sanskrit-Russian declension rules engine for Sanskrit loanwords in Russian.
  3. `DiacriticsMap`:
     - Bidirectional conversion between IAST, Cyrillic academic transliteration, and Devanagari.
- **Acceptance Gate**:
  - Sub-millisecond lookup latency for terminology queries.
  - Test suite validating declension cases for all terms in the seed dictionary.

---

### Phase 3: AI Provider Adapters & 4-Stage Translation Pipeline
- **Objective**: Implement pluggable AI provider adapters and orchestrate the 4-stage translation pipeline.
- **Key Deliverables**:
  1. `ITranslationProvider` interface and concrete adapters:
     - `GeminiProvider` (using native `google-genai`).
     - `AnthropicProvider` (using native `anthropic`).
     - `OpenAIProvider` (using native `openai`, also compatible with vLLM/Ollama).
  2. Resilient API calling layer with token-bucket rate-limiting and exponential backoff retry.
  3. Specialized pipeline stages:
     - `LiteralStage`: Extracts grammatical structure and literal word meanings.
     - `PhilosophicalStage`: Injects Gaudiya Siddhanta context and verifies personalist theology.
     - `LiteraryStage`: Formulates natural, dignified, elevated Russian literary prose.
     - `TerminologyStage`: Enforces BBT Russian orthography and diacritical precision.
  4. Prompt versioning system with Jinja2 templates.
- **Acceptance Gate**:
  - Translation of 10 golden test verses (from Gita and Bhagavatam) passes human theological inspection.
  - Mocked provider tests ensuring pipeline resilience against HTTP 429 and timeouts.

---

### Phase 4: Automated Quality Control & Auditing Engine
- **Objective**: Develop automated verification mechanisms to guarantee translation fidelity before publishing.
- **Key Deliverables**:
  1. `TerminologyAuditor`: Flags forbidden terms (e.g., Mayavada jargon) and unapproved spelling variants.
  2. `DiacriticsAuditor`: Validates completeness of Unicode diacritical marks in transliterated blocks.
  3. `VerseIntegrityAuditor`: Detects missing verse numbers, skipped lines, or concatenated verses.
  4. `HallucinationChecker`: Flags anomalous length ratios between source and target segments.
  5. `QCAuditReport`: Generates structured diagnostic reports in JSON and Markdown.
- **Acceptance Gate**:
  - Verification engine detects 100% of synthetic deliberate errors (injected wrong terms, stripped diacritics, dropped verses) in test fixtures.

---

### Phase 5: Publishing Engine & Multi-Format Exporters
- **Objective**: Transform translated Document AST into publication-ready files for commercial printing and digital reading.
- **Key Deliverables**:
  1. `DOCXExporter`: Formats text with customizable styles, running headers, footnotes, and verse callout boxes.
  2. `EPUBExporter`: Produces EPUB 3 packages with embedded TrueType/OpenType fonts for Devanagari and Cyrillic, fully validated via `epubcheck`.
  3. `PDFExporter`: Typesets dual-script pages with proper hyphenation and font embedding.
  4. `ParallelBilingualExporter`: Generates parallel text editions (Sanskrit original + Russian translation) for academic study.
- **Acceptance Gate**:
  - Exported DOCX opens cleanly in Microsoft Word and LibreOffice without formatting corruption.
  - Exported EPUB passes official EPUB 3 validation.

---

### Phase 6: Orchestration, CLI & Production Hardening
- **Objective**: Tie all subsystems together into a reliable, resumable command-line interface and test on end-to-end book translations.
- **Key Deliverables**:
  1. `JobManager`: Manages background jobs, concurrency, and persistent checkpoints in SQLite and JSONL.
  2. `Typer` CLI interface:
     - `vedic-translate start <input-file> --target ru --model gemini-2.5-pro`
     - `vedic-translate resume <job-id>`
     - `vedic-translate status <job-id>`
     - `vedic-translate export <job-id> --format docx,epub,pdf`
     - `vedic-translate glossary add / search / audit`
  3. Rich interactive terminal UI with live progress bars, tokens consumed, and audit findings.
  4. End-to-end integration test translating a full multi-chapter text.
- **Acceptance Gate**:
  - A process killed via `kill -9` or interrupted abruptly resumes without duplicating or omitting a single word.
  - Zero critical memory leaks over a 500-page translation job.
