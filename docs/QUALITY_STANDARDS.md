# Quality Standards & Verification Framework

**Project Name**: Vedic Book Translator  
**Quality Philosophy**: Non-Negotiable Philosophical Fidelity & Structural Invariance  
**Document Version**: 1.1.0 (Post-Audit Revision)  
**Status**: Revised Foundation  

---

## 1. Multi-Dimensional Translation Quality Framework

In translating sacred Vedic literature and Gaudiya Vaishnava commentaries, **automated numerical scores do NOT constitute proof of translation correctness**. 

A translation achieving a 99% glossary match can still suffer from subtle Mayavada contamination, awkward Anglicized phrasing, or misplaced syntactic agency. Quality is therefore decomposed into **six independent dimensions**, each with a distinct definition, validation methodology, known limitations, and remedial action:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                SIX INDEPENDENT QUALITY DIMENSIONS                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
         │                          │                          │                          │
         ▼                          ▼                          ▼                          ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ 1. LINGUISTIC    │       │ 2. PHILOSOPHICAL │       │ 3. TERMINOLOGY   │       │ 4. STRUCTURAL    │
│    ACCURACY      │       │    ACCURACY      │       │    CONSISTENCY   │       │    COMPLETENESS  │
└──────────────────┘       └──────────────────┘       └──────────────────┘       └──────────────────┘
         │                          │                          │                          │
         └──────────────────────────┼──────────────────────────┘                          │
                                    │                                                     │
                                    ▼                                                     ▼
                         ┌──────────────────┐                                  ┌──────────────────┐
                         │ 5. LITERARY      │                                  │ 6. HUMAN         │
                         │    QUALITY       │                                  │    APPROVAL      │
                         └──────────────────┘                                  └──────────────────┘
```

---

### Dimension 1: Linguistic Accuracy
- **Definition**: The degree to which the target Russian text accurately represents the grammatical relations, semantic predicates, verbal tenses, and case relationships of the source text (Sanskrit or English).
- **Validation Method**:
  - *Automated Diagnostic*: Cross-lingual syntactic dependency verification and entity extraction. Check for dropped negation particles (*na*, *mā*), inverted subject-object relations, and corrupted passive/active voice.
  - *Human Verification*: Expert bilingual philological review comparing Sanskrit verbal roots (*dhātus*) and case endings (*vibhakti*) against the Russian rendering.
- **Known Limitations of Automated Checks**: LLMs and parsers can misinterpret complex Sanskrit compound words (*bahuvrīhi* vs. *tatpuruṣa* vs. *karmadhāraya*).
- **Remediation**: Flagging ambiguous syntactic trees for human philological inspection.

---

### Dimension 2: Philosophical Accuracy (*Siddhānta-śuddhi*)
- **Definition**: The strict preservation of the personalist theology of the *Brahma-Mādhva-Gauḍīya-Sampradāya*, the ontological hierarchy (*acintya-bhedābheda-tattva*), and the insights of canonical Acharya commentaries (*ṭīkās*).
- **Validation Method**:
  - *Automated Diagnostic*: Semantic classifier specifically trained or prompted on Gaudiya theological contrast rubrics:
    - Verifying distinction between *Brahman* (effulgence), *Paramātmā* (localized Supersoul), and *Bhagavān* (Supreme Personality of Godhead).
    - Verifying distinction between *kāma* (lust/selfish desire) and *prema* (pure transcendental love).
    - Verifying that the individuality of the *jīva* is preserved (*nitya-dāsa*).
    - Screening for forbidden impersonal/Mayavada interpretations (e.g. "слияние с Богом", "иллюзия бытия", "космический разум").
  - *Human Verification*: Review and sign-off by a qualified Gaudiya Vaishnava scholar or editor.
- **Known Limitations of Automated Checks**: AI cannot grasp spiritual realization; subtle impersonalism can be masked by superficially pious vocabulary.
- **Remediation**: Immediate routing of flagged doctrinal anomalies to human theological review.

---

### Dimension 3: Terminology Consistency
- **Definition**: Exact, invariant conformance to the active **Orthography Profile** (e.g., Russian BBT profile vs. Academic Cyrillic profile) and project-specific glossaries across all chapters.
- **Validation Method**:
  - *Automated Diagnostic*: Deterministic token scanner auditing Sanskrit loanwords, names of personalities, sacred places, and philosophical terms against configured glossary tables.
  - *Morphological Check*: Running `pymorphy3` to confirm correct Russian declension cases without stem corruption (e.g., *прасада*, *вайшнавом*, *карме*).
- **Metric (Heuristic Only)**:
  $$\text{Terminology Consistency Score (TCS)} = \left( \frac{N_{\text{compliant\_terms}}}{N_{\text{total\_audited\_terms}}} \right) \times 100\%$$
- **Known Limitations**: Does not evaluate whether the chosen term is contextually elegant or natural.
- **Remediation**: Automated correction proposals with human confirmation.

---

### Dimension 4: Structural Completeness
- **Definition**: 100% preservation of all textual components, including original Devanagari meter (*ślokas*), Roman transliteration (*IAST*), word-for-word synonyms (*anvaya*), translation (*anuvāda*), commentaries (*tātparya*), verse numbering, headings, and footnotes.
- **Validation Method**:
  - *Automated Deterministic Invariant*: Strict Document AST schema validation.
  - Sequential verse continuity checks (detecting missed verses like skipping from 2.14 to 2.16).
  - Bidirectional element counting: Source segment count vs. target segment count.
- **Metric (Deterministic Invariant)**:
  $$\text{Structural Completeness Ratio} = 1.00 \quad (100\% \text{ required})$$
- **Known Limitations**: Does not measure internal text quality within a block.
- **Remediation**: Pipeline execution is blocked from exporting until structural invariants reach 100%.

---

### Dimension 5: Literary Quality & Russian Register
- **Definition**: The naturalness, fluency, rhythmic balance, and dignity of the translation in literary Russian prose, avoiding wooden machine-translation artifacts, Anglicisms, or anachronistic ecclesiastical jargon.
- **Validation Method**:
  - *Automated Diagnostic*: Stylistic heuristic scanning for repetitive syntax, excessive passive constructions ("это было сделано им"), unnatural prepositional chains, and lexical diversity.
  - *Human Verification*: Senior literary editor evaluation for rhythm, emotional resonance (*rasa*), and solemnity fitting sacred scripture.
- **Known Limitations**: Readability formulas (e.g., Flesch-Kincaid adapted for Russian) measure syllable lengths, not aesthetic beauty or devotional cadence.
- **Remediation**: Dedicated Literary Polish stage with human editorial revision.

---

### Dimension 6: Human Approval Gate
- **Definition**: The final, binding authorization required before any translation job can be compiled into distribution or publication formats.
- **Validation Method**:
  - A designated editor reviews the complete bilingual AST in a CLI diff or review UI.
  - The editor signs off on individual chapters or the entire document, transitioning blocks to `APPROVED`.
- **Rule**: No file marked solely by automated tools may be published as a final certified edition without human sign-off.

---

## 2. Engineering & Code Quality Standards

Every software component in the platform must comply with strict engineering guidelines:

- **Language Runtime**: Python 3.12+ with strict type annotations.
- **Static Analysis**: Enforced via **Ruff** (line length: 100) and **Mypy in strict mode** (`disallow_untyped_defs = true`, `check_untyped_defs = true`).
- **Data Validation**: Canonical domain models must inherit from `pydantic.BaseModel` (v2).
- **Error Handling**: Dedicated domain exception hierarchy rooted in `VedicTranslatorError`.
- **Zero Credential Hardcoding**: API keys and tokens must strictly be loaded from environment variables or local `.env` files via `pydantic-settings`.
- **Non-Destructive Ingestion**: Input documents are read-only; original text is immutable in AST nodes.

---

## 3. Testing Requirements

- **Unit Tests (`tests/unit/`)**: Target isolated parsers, segmenters, orthography mappers, and models. Execution must be instantaneous and have zero network dependencies.
- **Integration Tests (`tests/integration/`)**: Test end-to-end AST transitions using mock AI provider adapters and recorded golden fixtures.
- **Regression Tests (`tests/e2e/`)**: Validate pipeline behavior against canonical reference verses (*Bhagavad-gītā* 2.13, 9.22; *Śrīmad-Bhāgavatam* 1.1.1; *Caitanya-caritāmṛta* Ādi 1.1).
