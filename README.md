# Vedic Book Translator (Ведический книжный переводчик)

[![Architecture: Hexagonal](https://img.shields.io/badge/architecture-hexagonal-blue.svg)](docs/SYSTEM_ARCHITECTURE.md)
[![Python: 3.12](https://img.shields.io/badge/python-3.12+-green.svg)](pyproject.toml)
[![Quality: Rigorous](https://img.shields.io/badge/quality-automated%20audits-orange.svg)](docs/QUALITY_STANDARDS.md)
[![Methodology: 4-Stage](https://img.shields.io/badge/pipeline-4--stage%20translation-purple.svg)](docs/TRANSLATION_METHODOLOGY.md)

**Vedic Book Translator** is a specialized, production-grade AI-powered translation platform designed to translate classical Vedic literature, Sanskrit scriptures, and Acharya commentaries into Russian with uncompromising philosophical precision, literary elegance, and structural fidelity.

---

## 1. Vision & Mission

Vedic and Gaudiya Vaishnava scriptures—such as the *Bhagavad-gītā*, *Śrīmad-Bhāgavatam*, *Caitanya-caritāmṛta*, the *Upaniṣads*, and the commentaries (*ṭīkās*) of the Six Goswamis and later Acharyas—pose unique linguistic, theological, and typographical challenges that general-purpose translation tools fail to resolve:

1. **Complex Verse Structure**: Traditional texts alternate between original Sanskrit/Bengali meter (*ślokas*), Roman transliteration with diacritics (*IAST*), word-for-word synonyms (*anvaya*), translation (*anuvāda*), and extensive purports (*tātparya*).
2. **Theological Subtlety**: Translations must distinguish personalist (*tattva*) philosophy from Mayavada/impersonalist interpretations, correctly handling terms like *Brahman*, *Paramātmā*, *Bhagavān*, *rasa*, *bhakti*, *guṇa*, and *prakṛti*.
3. **Russian Vaishnava Tradition**: The Russian Vaishnava community has well-established orthographic and transliteration norms established by the Bhaktivedanta Book Trust (BBT), requiring exact Cyrillic representations (e.g., *Kṛṣṇa* → Кришна, *Caitanya* → Чайтанья, *jīva* → джива) and rigorous handling of diacritical marks.
4. **Volume and Continuity**: Books can exceed hundreds or thousands of pages. Maintaining consistent character names, epithets, terminology, and tone across chapters requires persistent book context and translation memory.

**Vedic Book Translator** solves these challenges by combining a modular **Hexagonal Architecture**, a **4-Stage Translation Pipeline**, persistent **Translation Memory**, and an automated **Quality Control Engine**.

---

## 2. Core Capabilities

- **Multi-Format Ingestion**: Ingests PDF (digital and scanned via OCR), EPUB, DOCX, and TXT files while retaining chapter hierarchy, footnotes, verse numbers, and formatting.
- **Provider-Agnostic AI Engine**: Plug-and-play adapters for Google Gemini, Anthropic Claude, OpenAI, and local/self-hosted LLMs (vLLM, Ollama) via unified interfaces.
- **4-Stage Translation Pipeline**:
  1. *Deconstructive Literal Translation*: Strict semantic breakdown preserving grammatical nuances.
  2. *Theological & Philosophical Review*: Alignment with Gaudiya Vaishnava Siddhanta and commentary context.
  3. *Literary Russian Stylization*: High-register Russian prose avoiding secular idioms, anachronisms, or church archaisms.
  4. *Terminology & Diacritic Harmonization*: Automated audit against BBT glossaries and IAST diacritical standards.
- **Non-Destructive AST Processing**: Preserves original texts, parallel layouts, Sanskrit verses, and creates bi-lingual or annotated editions.
- **Persistent Book Memory & Glossaries**: Dynamic context injection, chapter-level entity memory, and local translation memory (TM) caching.
- **Resumable Batch Orchestration**: Job state checkpoints allow processing massive books over multiple sessions with zero loss of progress.
- **Automated Quality Control**: Algorithmic checks for missing verses, hallucinations, terminology drift, and diacritics completeness.
- **Multi-Format Publishing**: Export directly to publication-ready DOCX, EPUB, and PDF formats with proper Devanagari and Cyrillic font embedding.

---

## 3. High-Level Architecture Overview

```
                                  +-----------------------------+
                                  |     Source Input File       |
                                  |  (PDF, EPUB, DOCX, TXT)     |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |     Document Processor      |
                                  |   (Parsers, OCR, Segmenter) |
                                  +--------------+--------------+
                                                 |
                                      Document AST (IR)
                                                 |
                                                 v
+------------------------+        +-----------------------------+        +------------------------+
|   Translation Memory   |<------>|     Translation Engine      |<------>|    AI Model Adapters   |
|   & Terminology DB     |        |   (4-Stage Multi-LLM Pipe)  |        | (Gemini, Claude, GPT)  |
+------------------------+        +--------------+--------------+        +------------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |   Quality Control System    |
                                  | (Diacritics, Drift, Verses) |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |      Publishing Engine      |
                                  |   (DOCX, EPUB, PDF Output)  |
                                  +-----------------------------+
```

---

## 4. Repository Structure

```
vedic-book-translator/
├── .env.example              # Template for environment variables and API keys
├── .gitignore                # Git ignore rules for Python, IDEs, and artifacts
├── AGENTS.md                 # Operating guidelines for AI agents & contributors
├── CHANGELOG.md              # Version history following Keep a Changelog
├── README.md                 # Project overview and entry point (this file)
├── pyproject.toml            # Project dependencies, build specs, tool configs
├── configs/                  # Configuration YAML files (pipeline, logging, models)
├── glossaries/               # Curated Gaudiya Vaishnava terminology & rules
├── docs/                     # Comprehensive architectural & procedural docs
│   ├── PRODUCT_REQUIREMENTS.md    # Detailed specifications and use cases
│   ├── SYSTEM_ARCHITECTURE.md     # Component architecture and sequence flows
│   ├── DEVELOPMENT_ROADMAP.md     # Phased milestone delivery plan
│   ├── TRANSLATION_METHODOLOGY.md # 4-Stage linguistic & theological process
│   ├── QUALITY_STANDARDS.md       # Coding, testing, and translation metrics
│   └── DECISIONS.md               # Architecture Decision Records (ADRs)
├── src/
│   └── vedic_translator/     # Python source package
│       ├── core/             # Base models, config, exceptions, logging
│       ├── document_processor/ # Extractors, OCR, semantic segmentation
│       ├── translation_engine/ # Adapters, prompt engine, 4-stage pipeline
│       ├── memory_glossary/  # Terminology DB, translation memory, context store
│       ├── quality_control/  # Hallucination, verse, diacritic auditors
│       ├── publishing_engine/ # DOCX, EPUB, PDF exporters & typography
│       └── orchestrator/     # Job lifecycle, checkpointing, CLI runner
└── tests/                    # Unit, integration, e2e tests & golden fixtures
```

---

## 5. Documentation Directory

For in-depth details, please consult our documentation suite:

| Document | Description |
| :--- | :--- |
| [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Product scope, functional requirements, user personas, edge cases |
| [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | Subsystems, interfaces, data flow, AST design, error handling |
| [DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Milestone phases (Phase 0 to Phase 6), deliverables, acceptance gates |
| [TRANSLATION_METHODOLOGY.md](docs/TRANSLATION_METHODOLOGY.md) | 4-Stage methodology, Gaudiya theology, Sanskrit verse parsing rules |
| [QUALITY_STANDARDS.md](docs/QUALITY_STANDARDS.md) | Code quality, test coverage requirements, QA metrics, verification |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records (ADR-001 through ADR-008) |
| [AGENTS.md](AGENTS.md) | Guidelines, boundaries, and checklists for AI development agents |

---

## 6. Current Status & Next Steps

This project is currently at **Phase 0 (Initialization & Architectural Foundation)**. 

No application code will be executed until the architecture, technology stack, and product specifications have been formally approved. Once approved, development will proceed to **Phase 1: Document Processing & AST Modeling**.
