# Product Requirements Document (PRD)

**Project Name**: Vedic Book Translator  
**Target Languages**: English to Russian, Sanskrit to Russian, Bengali/Brajabhasha to Russian  
**Domain**: Vedic Literature, Classical Sanskrit Texts, Gaudiya Vaishnava Theology and Commentaries  
**Document Version**: 1.0.0  
**Status**: Pending Architecture Approval  

---

## 1. Executive Summary & Problem Statement

### 1.1 The Challenge
Translating sacred and philosophical literature—specifically Vedic texts (*Vedas*, *Upaniṣads*, *Purāṇas*, *Bhagavad-gītā*) and the extensive canon of the Gaudiya Vaishnava Acharyas (Śrī Caitanya Mahāprabhu, the Six Goswamis of Vrindavan, Śrīla Viśvanātha Cakravartī Ṭhākura, Śrīla Bhaktivinoda Ṭhākura, and Śrīla A.C. Bhaktivedanta Swami Prabhupāda)—presents extreme linguistic, theological, and typographical complexities that general-purpose AI and translation tools fail to navigate:

1. **Theological Inaccuracy & Bias**: Generic LLMs and translation engines regularly flatten personalist Gaudiya Siddhanta into generic impersonalism or Advaita Vedānta. Key philosophical terms like *Brahman*, *Paramātmā*, and *Bhagavān* are conflated as "God" or "Cosmic Mind", destroying crucial theological distinctions.
2. **Structural Destruction of Sacred Meter**: Classical texts adhere to a strict pedagogical five-tier structure:
   - Original Sanskrit/Bengali meter (*Mūla-śloka* in Devanagari/Bengali script).
   - International Alphabet of Sanskrit Transliteration (*IAST*) with precise diacritics.
   - Word-for-word Sanskrit-to-Russian lexical equivalents (*Anvaya* / *Pada-artha*).
   - Literary prose translation (*Anuvāda*).
   - Exhaustive commentary and philosophical explanation (*Tātparya* / *Ṭīkā*).  
   Standard translation tools treat this as unstructured text, mangling verse divisions, misaligning word-for-word correspondences, and losing numbering.
3. **Diacritical and Typographical Degradation**: Sanskrit and Bengali require exact diacritical marks (e.g., ā, ī, ū, ṛ, ṝ, ḷ, ḹ, ṅ, ñ, ṭ, ḍ, ṇ, ś, ṣ, ḥ, ṁ). Furthermore, Russian scholarly and devotional publications follow established BBT (Bhaktivedanta Book Trust) transliteration standards and Cyrillic diacritic conventions. Standard tools routinely strip or distort these marks.
4. **Volume and Contextual Drift**: A complete Vedic scripture often spans hundreds or thousands of pages (e.g., *Śrīmad-Bhāgavatam* consists of 18,000 verses across 12 Cantos). Translating such works in isolated chunks causes drastic terminology drift, inconsistent character names, fluctuating registers, and loss of narrative continuity.
5. **Rigid or Wooden Russian Syntax**: Literal machine translation yields unnatural, Anglicized, or stilted Russian that alienates native readers. The translation must balance strict philological fidelity with the graceful, dignified cadence of classical Russian literary and theological prose.

### 1.2 The Solution
**Vedic Book Translator** is a specialized, autonomous, and modular platform built around a **4-Stage Translation Pipeline**, persistent **Book Context Memory**, and strict **Quality Control Auditing**. It guarantees that every verse, synonym, commentary, and philosophical nuance is preserved and rendered into publication-ready Russian.

---

## 2. User Personas & Target Audiences

| Persona | Role | Primary Needs | Critical Success Factor |
| :--- | :--- | :--- | :--- |
| **Dr. Elena (Vedic Scholar)** | Academic Sanskritologist & Translator | Philological accuracy, exact *anvaya* (word-for-word) parsing, diacritic integrity, preserving variant readings. | Zero loss of grammatical nuance; 100% preservation of IAST and Devanagari. |
| **Vyacheslav (Publishing Editor)** | Senior Editor at a Vaishnava Publishing House (e.g., BBT) | Adherence to BBT Russian orthography, literary Russian style, consistent terminology across 50+ chapters, publication-ready DOCX/EPUB export. | Automated terminology enforcement; elimination of manual proofreading cycles for standard terms. |
| **Bhakti-lata (Monastic Archivist)** | Temple Historian & Book Conservator | Digitize, OCR, and translate scanned historical commentaries and archival manuscripts. | High-accuracy OCR on aged Sanskrit/English scans; non-destructive handling of source documents. |
| **Maxim (Devotional Reader)** | Practitioner of Bhakti-yoga | Deep, inspiring, readable Russian translations with lucid philosophical explanations and readable typography. | Natural, dignified Russian prose without awkward English syntax or dry mechanical language. |

---

## 3. Scope of Literature & Supported Formats

### 3.1 Literature Domain
1. **Canonical Scriptures**: *Śrīmad Bhagavad-gītā*, *Śrīmad-Bhāgavatam*, *Śrī Caitanya-caritāmṛta*, *Śrī Īśopaniṣad*, *Brahma-saṁhitā*.
2. **Goswami Literature**: Works of Śrī Rūpa Gosvāmī (*Bhakti-rasāmṛta-sindhu*, *Upadeśāmṛta*), Śrī Sanātana Gosvāmī (*Bṛhad-bhāgavatāmṛta*), Śrī Jīva Gosvāmī (*Ṣaṭ-sandarbhas*).
3. **Acharya Commentaries**: Classical *ṭīkās* by Śrīdhara Svāmī, Viśvanātha Cakravartī Ṭhākura, Baladeva Vidyābhūṣaṇa, Bhaktivinoda Ṭhākura, Bhaktisiddhānta Sarasvatī Ṭhākura, and A.C. Bhaktivedanta Swami Prabhupāda.
4. **Modern Philosophical Treatises**: English monographs, lectures, essays, and letters on Vedic sociology (*Varṇāśrama*), metaphysics, cosmology, and epistemology.

### 3.2 Supported Formats
- **Input Formats**:
  - `PDF`: Digital vector PDFs (extracting embedded text, hierarchy, fonts) and scanned image PDFs (processed via OCR).
  - `EPUB`: EPUB 2 and EPUB 3 (preserving chapter navigation, semantic HTML, and metadata).
  - `DOCX`: Microsoft Word documents (preserving heading hierarchy, italics, footnotes, and lists).
  - `TXT / MD`: Clean plain text or Markdown files with structural conventions.
- **Output Formats**:
  - `DOCX`: Styled for publication layout, footnote links, custom styles for verses, synonyms, and purports.
  - `EPUB 3`: Reflowable e-book adhering to IDPF standards with embedded Unicode fonts.
  - `PDF`: Typeset PDF with dual-script support (Devanagari + Cyrillic), running headers, and page numbering.
  - `Bilingual Parallel Edition`: Side-by-side or stacked source-and-translation view for study and scholarly comparison.

---

## 4. Functional Requirements

### FR-01: Document Ingestion & Optical Character Recognition (OCR)
- **FR-01.1**: Ingest PDF, EPUB, DOCX, and TXT files without modifying or altering the source files.
- **FR-01.2**: Extract document metadata (title, author, publisher, ISBN, language, year).
- **FR-01.3**: For scanned documents or non-searchable PDFs, execute high-accuracy OCR supporting mixed scripts: Devanagari (Sanskrit), Latin (IAST), and Cyrillic (Russian).
- **FR-01.4**: Remove OCR artifacts, hyphenation at line breaks, and page header/footer intrusions while preserving actual footnotes.

### FR-02: Structural & Semantic Text Segmentation
- **FR-02.1**: Parse the document into a hierarchical **Document Abstract Syntax Tree (AST)** composed of Chapters, Sections, and Semantic Blocks.
- **FR-02.2**: Classify each semantic block into a typed entity:
  - `VERSE_DEVANAGARI`: Original Sanskrit/Bengali meter.
  - `VERSE_IAST`: Roman transliteration with diacritics.
  - `SYNONYMS`: Word-for-word lexical equivalents (*anvaya*).
  - `TRANSLATION`: Literary prose translation (*anuvāda*).
  - `PURPORT`: Commentary and philosophical explanation (*tātparya*).
  - `HEADING`: Chapter and section titles.
  - `PARAGRAPH`: Standard narrative prose.
  - `FOOTNOTE`: Numbered explanatory notes.
- **FR-02.3**: Support multi-verse bindings (e.g., "Verses 4–6 translated together").
- **FR-02.4**: Maintain verse numbering continuity and flag missing, skipped, or duplicated verse numbers.

### FR-03: Persistent Book Context & Entity Memory
- **FR-03.1**: Establish a persistent **Book Context Store** that maintains character genealogies, geographical locations, recurring metaphors, and philosophical themes across all chapters.
- **FR-03.2**: Automatically generate and dynamically update a **Dramatis Personae & Entity Register** (e.g., identifying when *Pārtha*, *Guḍākeśa*, and *Dhanañjaya* all refer to Arjuna).
- **FR-03.3**: Inject relevant chapter-level and book-level context into the translation prompt of each individual segment to prevent contextual blindness.

### FR-04: 4-Stage Multi-LLM Translation Pipeline
- **Stage 1 (Literal Parsing)**: Perform rigorous morphological and syntactic deconstruction of the source text, ensuring every Sanskrit compound and English clause is mapped accurately.
- **Stage 2 (Philosophical & Theological Review)**: Audit the translation against Gaudiya Vaishnava Siddhanta, verifying that personalist philosophy is preserved, Acharya commentary nuance is honored, and impersonalist phrasing is eliminated.
- **Stage 3 (Literary Russian Stylization)**: Refine the text into elevated, elegant, and natural Russian literary prose, conforming to classical grammatical norms while avoiding modern colloquialisms or archaic Orthodox ecclesiastical jargon.
- **Stage 4 (Terminology & Diacritics Enforcement)**: Harmonize all specialized terms against the approved terminology database, enforcing BBT Russian transliteration rules (e.g., *Kṛṣṇa* → Кришна) and verifying Unicode diacritic accuracy.

### FR-05: Translation Memory (TM) & Segment Deduplication
- **FR-05.1**: Store all translated segments (source text hash, source language, target text, metadata) in a persistent Translation Memory (TM).
- **FR-05.2**: Perform exact-match and fuzzy-match lookups before sending segments to the AI provider. If an exact match exists from an approved source, reuse it to save time and API costs.
- **FR-05.3**: Maintain an audit trail of which segments were retrieved from TM versus generated by AI.

### FR-06: Terminology Database & BBT Orthography Engine
- **FR-06.1**: Maintain a comprehensive database of Gaudiya Vaishnava philosophical terms, proper names, sacred places, and scriptural titles.
- **FR-06.2**: Provide bidirectional mappings: Sanskrit (Devanagari & IAST) ↔ English ↔ Russian (BBT standard and academic standard).
- **FR-06.3**: Enforce Russian declension rules on Sanskrit loanwords (e.g., nominative *бхакти*, genitive *бхакти*; nominative *прасад*, genitive *прасада*).
- **FR-06.4**: Support user-defined custom glossaries per book project.

### FR-07: Resumable Execution & Job Checkpointing
- **FR-07.1**: The system must persist job state after every segment, section, or chapter.
- **FR-07.2**: In the event of network disruption, rate-limiting, process termination, or crash, the system must resume from the exact last incomplete segment without re-translating completed work.
- **FR-07.3**: Provide CLI commands to inspect job status: `status`, `pause`, `resume`, `retry-failed`, and `export`.

### FR-08: Automated Quality Control & Auditing
- **FR-08.1**: **Terminology Compliance Audit**: Scan translated text for unauthorized term variations or forbidden translations.
- **FR-08.2**: **Diacritics Verification**: Verify that every Sanskrit/IAST term retains its proper diacritical marks in footnotes, transliteration blocks, and bracketed explanations.
- **FR-08.3**: **Hallucination & Omission Detection**: Compare source and target length, paragraph counts, and sentence structures to detect missing text or fabricated content.
- **FR-08.4**: **Verse Integrity Check**: Confirm that all verses present in the source document exist in the target document with matching identifiers.

### FR-09: Human-in-the-Loop (HITL) Review Interface
- **FR-09.1**: Flag segments with low confidence scores or terminology conflicts for human review.
- **FR-09.2**: Allow editors to inspect the source, literal translation, theological notes, and final text side-by-side.
- **FR-09.3**: Record editor corrections directly back into the Translation Memory and Terminology Database to improve subsequent translations.

### FR-10: Multi-Format Publishing Engine
- **FR-10.1**: Generate publication-ready `.docx` files adhering to professional book design: dedicated paragraph styles for verses, word-for-word blocks, translations, purports, and footnotes.
- **FR-10.2**: Generate validated `.epub` files (EPUB 3) with reflowable layout, valid table of contents, and embedded fonts.
- **FR-10.3**: Generate print-ready `.pdf` files featuring true Devanagari fonts (e.g., Siddhanta, Murty Sanskrit) and Cyrillic typography with diacritic support.
- **FR-10.4**: Generate bilingual parallel layouts (facing pages or stacked blocks).

### FR-11: Provider-Agnostic Model Adapters
- **FR-11.1**: Support Google Gemini (Gemini 2.5 Pro / Flash), Anthropic Claude (Claude 3.7 Sonnet / Haiku), and OpenAI (GPT-4o) through unified abstract interfaces.
- **FR-11.2**: Support local and open-source models via OpenAI-compatible endpoints (vLLM, Ollama, LM Studio).
- **FR-11.3**: Support model routing: assign different models to different pipeline stages (e.g., Gemini for high-context extraction, Claude for deep theological reasoning, GPT-4o for Russian stylistic polish).

---

## 5. Non-Functional Requirements

### NFR-01: Accuracy & Fidelity
- **Zero Theological Distortion**: Translations must adhere to the authorized Gaudiya Siddhanta. Any introduction of Mayavada/impersonalist phrasing is treated as a critical defect.
- **100% Structural Completeness**: Zero omitted verses, zero lost footnotes, and zero corrupted numbering.

### NFR-02: Performance & Scalability
- **Large Book Handling**: Capable of processing books exceeding 1,000 pages (500,000+ words) without out-of-memory errors.
- **Throughput**: Support configurable concurrency with token bucket rate-limiting to maximize API throughput while respecting provider limits.
- **Storage Footprint**: Efficient local storage using SQLite for metadata, translation memory, and job checkpoints.

### NFR-03: Security & Privacy
- **Zero Credential Leakage**: No API keys or access tokens stored in code, logs, or repository.
- **Data Protection**: Local processing of documents; only necessary text segments are transmitted over secure TLS connections to approved AI endpoints.

### NFR-04: Reliability & Fault Tolerance
- **Idempotency**: Rerunning a completed or partially completed job must never produce duplicate chapters or corrupted state.
- **Graceful Degradation**: If an AI provider experiences high latency or rate limits, the system must execute exponential backoff with jitter and, if configured, failover to a backup provider.

### NFR-05: Maintainability & Extensibility
- **Hexagonal Architecture**: Business logic isolated from frameworks, databases, and third-party AI SDKs.
- **Strict Typing**: 100% type annotations validated by Mypy in strict mode.

---

## 6. Structural Vedic Text Model Specification

To ensure standard processing across all modules, every Vedic text is mapped to the following canonical schema:

```
+-------------------------------------------------------------------------+
|                              CHAPTER                                    |
|  +-------------------------------------------------------------------+  |
|  | Heading: Chapter 2. Contents of the Gita Summarized               |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | SECTION: Verse 13                                                 |  |
|  |                                                                   |  |
|  | 1. VERSE_DEVANAGARI:                                              |  |
|  |    देहिनोऽस्मिन्यथा देहे कौमारं यौवनं जरा ।                           |  |
|  |    तथा देहान्तरप्राप्तिर्धीरस्तत्र न मुह्यति ॥ १३ ॥                 |  |
|  |                                                                   |  |
|  | 2. VERSE_IAST:                                                    |  |
|  |    dehino 'smin yathā dehe kaumāraṁ yauvanaṁ jarā                |  |
|  |    tathā dehāntara-prāptir dhīras tatra na muhyati               |  |
|  |                                                                   |  |
|  | 3. SYNONYMS (Anvaya):                                             |  |
|  |    dehinaḥ — of the embodied; asmin — in this; yathā — as;        |  |
|  |    dehe — in the body; kaumāram — boyhood; yauvanam — youth;      |  |
|  |    jarā — old age; tathā — similarly; dehāntara — of another     |  |
|  |    body; prāptiḥ — achievement; dhīraḥ — the sober;              |  |
|  |    tatra — thereupon; na — never; muhyati — is deluded.           |  |
|  |                                                                   |  |
|  | 4. TRANSLATION (Anuvāda):                                         |  |
|  |    Воплотившаяся в теле душа постепенно меняет тело отрочества   |  |
|  |    на тело юности, а затем на тело старости. Точно так же после   |  |
|  |    смерти она переходит в другое тело. Трезвомыслящего человека   |  |
|  |    такая перемена не смущает.                                     |  |
|  |                                                                   |  |
|  | 5. PURPORT (Tātparya):                                            |  |
|  |    Каждое живое существо — это индивидуальная душа...            |  |
|  |    [Detailed philosophical commentary with citations]             |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 7. Edge Cases & Risk Scenarios

1. **Multi-Verse Units**: Classical texts often group 2 to 5 verses together under a single translation and commentary (e.g., *BG 1.4–6*). The AST parser must bind these verses into a single compound block without breaking sequential indexing.
2. **Prose Commentaries with Embedded Verses**: Commentaries frequently quote secondary verses from the *Upaniṣads* or *Purāṇas* inline. The segmenter must identify and distinguish main canonical verses from secondary supporting quotations.
3. **Compound Sanskrit Words (*Samāsa*)**: Long Sanskrit compounds require proper hyphenation and breakdown in word-for-word synonyms.
4. **Historical & Non-Standard Transliterations**: Older books use non-standard transliterations (e.g., Balaram font encoding, Harvard-Kyoto, or plain Latin without diacritics). The ingestion engine must normalize all Romanized Sanskrit to canonical Unicode IAST.
5. **Russian Declension of Untranslated Sanskrit Nouns**: Terms like *кармы*, *бхакти*, *вайшнава*, *дхарму*, *брахмачари* must be declined according to standard Russian grammatical cases without corrupting the stem.
