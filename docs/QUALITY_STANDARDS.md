# Quality Standards & Verification Framework

**Project Name**: Vedic Book Translator  
**Quality Philosophy**: Zero-Tolerance for Theological Distortion & Structural Omission  
**Target Coverage**: Minimum 85% Code Coverage; 100% Invariant Validation on Sacred Verses  
**Document Version**: 1.0.0  
**Status**: Pending Architecture Approval  

---

## 1. Engineering & Code Quality Standards

Every line of code committed to this repository must satisfy strict static analysis, type checking, and architectural rules.

### 1.1 Python Language Standards
- **Runtime**: Python 3.12+
- **Style Guide**: PEP 8 enforced via **Ruff** with a maximum line length of 100 characters.
- **Type Checking**: Strict mode enforced via **Mypy**:
  - `disallow_untyped_defs = true`
  - `disallow_incomplete_defs = true`
  - `check_untyped_defs = true`
  - `no_implicit_optional = true`
  - `warn_redundant_casts = true`
  - `warn_unused_ignores = true`
  - `warn_return_any = true`
- **Data Modeling**: All domain entities, AST nodes, configuration objects, and API schemas must inherit from `pydantic.BaseModel` (v2) with strict field validation.

### 1.2 Exception Handling Protocol
All exceptions in the system must derive from a single root domain exception: `VedicTranslatorError`.

```
VedicTranslatorError (Base)
├── IngestionError
│   ├── UnsupportedFormatError
│   ├── CorruptedDocumentError
│   └── OCREngineError
├── SegmentationError
│   ├── MalformedVerseStructureError
│   └── InconsistentVerseNumberingError
├── ProviderError
│   ├── RateLimitExceededError
│   ├── AuthenticationError
│   └── ProviderTimeoutError
├── PipelineError
│   ├── StageExecutionError
│   └── ContextInjectionError
├── QualityControlError
│   ├── TerminologyViolationError
│   ├── MissingDiacriticsError
│   └── HallucinationDetectedError
└── PublishingError
    ├── FontEmbeddingError
    └── ExportValidationError
```

- **Rule**: Catching bare `Exception` is strictly forbidden except at the top-level CLI runner boundary.
- **Rule**: Exceptions must provide actionable diagnostic messages, including document name, chapter index, and block ID.

### 1.3 Logging Standards
- **Engine**: Structured logging powered by `loguru`.
- **Formatting**: JSON output in automated environments; colored, human-readable terminal output during local CLI execution.
- **Privacy & Security**: Never log raw API keys, bearer tokens, or full un-redacted user files.

---

## 2. Testing Architecture & Verification Protocols

The test suite is structured into three distinct tiers:

```
                  +-----------------------------------+
                  |         E2E Golden Tests          |  (Complete chapters from
                  |     (Verse Invariant Checks)      |   Gita & Bhagavatam)
                  +-----------------+-----------------+
                                    |
                  +-----------------+-----------------+
                  |      Integration Test Suite       |  (Mocked AI Providers,
                  |  (AST Pipeline, TM & QC Audits)   |   SQLite persistence)
                  +-----------------+-----------------+
                                    |
                  +-----------------+-----------------+
                  |         Unit Test Suite           |  (Parsers, Segmenters,
                  |     (Pure Functions & Mappers)    |   Orthography Rules, Models)
                  +-----------------------------------+
```

### 2.1 Unit Tests (`tests/unit/`)
- Target isolated components without network or disk I/O.
- Test coverage must exceed 85% across all core packages.
- Test suites must execute within seconds using `pytest`.

### 2.2 Integration Tests (`tests/integration/`)
- Verify interactions between subsystems:
  - Parsing a sample PDF/DOCX file and verifying the generated Document AST.
  - Querying and persisting entries into the SQLite Translation Memory.
  - Simulating the 4-stage pipeline using recorded provider responses (mock fixtures).
  - Executing automated QC checks against deliberately corrupted test cases.

### 2.3 E2E Golden Verification (`tests/e2e/`)
- Golden tests run against authoritative, verified benchmark texts:
  - *Bhagavad-gītā*, Chapter 2, Verses 11–25 (Classical verse structure, complex *anvaya*, profound philosophy).
  - *Śrīmad-Bhāgavatam*, Canto 1, Chapter 1, Verse 1 (Theological synthesis of *janmādy asya yataḥ*).
  - *Śrī Caitanya-caritāmṛta*, Ādi-līlā, Chapter 1, Verse 1 (Bengali/Sanskrit bilingual structure).
- E2E tests verify that the output meets all translation metrics defined in Section 3.

---

## 3. Automated Translation Quality Metrics

The Quality Control Engine evaluates every completed translation block against four quantitative metrics:

### 3.1 Terminology Fidelity Index (TFI)
Measures the percentage of specialized Vedic and Gaudiya Vaishnava terms translated in exact compliance with the approved glossary:

$$\text{TFI} = \left( \frac{N_{\text{valid\_terms}}}{N_{\text{total\_terms}}} \right) \times 100\%$$

- **Acceptance Threshold**: $\ge 99.0\%$
- **Enforcement**: Any presence of forbidden Mayavada translations (e.g., translating *Brahman* as generic "God" or *bhakti* as "idolatry/sect") triggers an immediate validation failure.

### 3.2 Diacritics Completeness Score (DCS)
Measures the preservation and correctness of Unicode diacritical marks in transliterated Sanskrit text (*IAST*) and scholarly Cyrillic notation:

$$\text{DCS} = \left( \frac{N_{\text{valid\_diacritics}}}{N_{\text{expected\_diacritics}}} \right) \times 100\%$$

- **Acceptance Threshold**: $100.0\%$ for `VERSE_IAST` and `SYNONYMS` blocks; $\ge 98.0\%$ for citations within `PURPORT` blocks.
- **Monitored Characters**: `ā, ī, ū, ṛ, ṝ, ḷ, ḹ, ṅ, ñ, ṭ, ḍ, ṇ, ś, ṣ, ḥ, ṁ`.

### 3.3 Verse Structural Invariance (VSI)
Verifies that all structural components of canonical verse units are present and correctly ordered:

$$\text{VSI} = \frac{\sum \text{Present Components}}{\sum \text{Expected Components}} \times 100\%$$

- **Acceptance Threshold**: $100.0\%$
- **Invariants**:
  - No dropped verses or missed line numbers.
  - Multi-verse spans (e.g., verses 4–6) must match between source and target.
  - Word-for-word synonyms must match the lexical tokens in the transliterated verse.

### 3.4 Hallucination & Omission Ratio (HOR)
Measures anomalous expansions or omissions by comparing character counts, word counts, and semantic density:

$$\text{Ratio} = \frac{\text{Length}(\text{Russian Target})}{\text{Length}(\text{Source Text})}$$

- **Normal Bounds**:
  - English to Russian: $1.05 \le \text{Ratio} \le 1.35$ (Russian prose is typically 10–25% longer than English due to morphology).
  - Sanskrit Verse to Russian Translation: Monitored via sentence count and semantic similarity rather than character length.
- Any segment with $\text{Ratio} > 1.60$ or $\text{Ratio} < 0.85$ is flagged for human review as a potential hallucination or truncation.

---

## 4. Human-in-the-Loop (HITL) Review Protocol

While the translation engine is autonomous, certain high-ambiguity situations require human editorial intervention:

```
[Translation Completed]
          |
          v
[Automated QC Audit]
          |
    +-----+-----+
    |           |
[PASS]       [FAIL or Low Confidence]
    |           |
    |           v
    |     [Flagged for HITL Review]
    |           |
    |     [Editor Approves / Edits in CLI or Review UI]
    |           |
    +-----> [Update Translation Memory & Terminology DB]
          |
          v
    [Release to Publishing Engine]
```

### 4.1 Trigger Conditions for Human Review
1. **Critical QC Failure**: Any block failing TFI, DCS, or VSI thresholds.
2. **Ambiguous Polysemy**: The AI models report low confidence or conflicting readings in Stage 2.
3. **New Uncataloged Terms**: Terms identified as philosophical or sacred that do not exist in `glossaries/`.
4. **Complex Multi-Verse Merges**: Scanned texts with ambiguous verse boundaries.

### 4.2 Feedback Loop
When a human editor modifies a flagged block:
1. The corrected text immediately updates the Document AST.
2. The corrected pair (source text + editor translation) is committed to the Translation Memory with `provenance="human_editor"`.
3. If new terms were defined, they are added to the project's local glossary.
