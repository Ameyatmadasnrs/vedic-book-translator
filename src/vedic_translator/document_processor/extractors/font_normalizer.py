"""Legacy PDF font normalization service for Chanakya and Nalanda encodings.

Provides deterministic, offline span-level conversion of legacy 8-bit visual encodings
used in historic Indian publications (such as Gita Press editions) into standard
Unicode Devanagari (U+0900..U+097F) and standard IAST Roman transliteration.
"""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable

# ==============================================================================
# Chanakya (Devanagari) Conversion Tables & Constants
# ==============================================================================

# Multi-glyph structural ligatures and stem combinations
CHANAKYA_PRE_REPLACEMENTS: list[tuple[str, str]] = [
    # Metrical prefix abbreviation combinations (Doha, Chaupai, Chhanda, Soratha)
    ("ŒÙ0", "दो०"),
    ("øı0", "चौ०"),
    ("¿¢U0", "छं०"),
    ("¿¢0", "छं०"),
    ("‚Ù0", "सो०"),
    # Two-part split matras (Ê +  -> ो, Ê + \uf8ff -> ो, Ê + Ò -> ौ)
    ("Ê\uf8ff", "ो"),
    ("Ê", "ो"),
    ("ÊÒ", "ौ"),
    # Nukta consonants (ड़ and ढ़)
    ("«U∏", "ड़"),
    ("« ∏", "ड़"),
    ("«∏U", "ड़"),
    ("«∏", "ड़"),
    ("…U∏", "ढ़"),
    ("… ∏", "ढ़"),
    ("…∏U", "ढ़"),
    ("…∏", "ढ़"),
    # Hri
    ("NU", "हृ"),
    ("N", "हृ"),
    # Kta
    ("Q§", "क्त"),
    ("Q", "क्त"),
    # Tta
    ("ûÊ", "त्त"),
    ("û", "त्त"),
    # Sra
    ("dﬂ", "स्रव"),
    ("d", "स्र"),
    # Shva
    ("EÊ", "श्वा"),
    ("E", "श्व"),
    # Dbha
    ("jﬂ", "द्भव"),
    ("jÈ", "द्भु"),
    ("j", "द्भ"),
    # Sna
    ("FÊ", "स्ना"),
    ("F", "स्न"),
    # Dga
    ("eÈL¢§", "द्गुरुं"),
    ("eÈ", "द्गु"),
    ("e", "द्ग"),
    # Hma
    ("rÊÔÊ", "ह्मा"),
    ("rÊÔ", "ह्म"),
    ("rÔ", "ह्म"),
    ("r", "ह्म"),
    # Kka
    ("P§", "क्क"),
    ("P", "क्क"),
    # Shta
    ("CÔU", "ष्ट"),
    ("CÔ", "ष्ट"),
    ("C", "ष्ट"),
    # Shkha
    ("WÔ", "ङ्ख"),
    ("W", "ङ्ख"),
    # Hla
    ("tÔU", "ह्ल"),
    ("tÔ", "ह्ल"),
    # Hna
    ("qÔU", "ह्न"),
    ("qÔ", "ह्न"),
    # Na / Pna
    ("AÊ", "्ना"),
    ("A", "्न"),
    # Ya in Awadhi
    ("KÙ", "्यो"),
    ("KÕZ", "यर्थ"),
    ("K", "्य"),
    # Reph / Nasal on I
    ("ßZ", "ईं"),
    # Subscript Nka
    ("VÔ", "ङ्क"),
    ("V", "ङ्क"),
    # Top-matra combinations for Ka (∑ ... §)
    ("∑§", "के"),
    ("∑Ò§", "कै"),
    ("∑È§", "कु"),
    ("∑Í§", "कू"),
    ("∑Î§", "कृ"),
    ("∑§ı", "कौ"),
    ("∑§Ù", "को"),
    ("∑§Ê", "का"),
    ("∑§Ë", "की"),
    ("∑§¢", "कं"),
    ("∑§", "क"),
    ("∑", "क"),
    # Top-matra combinations for Ra (⁄ ... U)
    ("⁄¥U", "रें"),
    ("⁄U", "रे"),
    ("⁄Ò¥U", "रैं"),
    ("⁄ÒU", "रै"),
    ("⁄ÙU", "रो"),
    ("⁄ıU", "रौ"),
    ("⁄ÈU", "रु"),
    ("⁄È", "रु"),
    ("⁄ÍU", "रू"),
    ("⁄Í", "रू"),
    ("⁄UÊ", "रा"),
    ("⁄UË", "री"),
    ("⁄U", "र"),
    ("⁄", "र"),
    # Top-matra combinations for Ha („ ... U)
    ("„¥U", "हें"),
    ("„U", "हे"),
    ("„Ò¥U", "हैं"),
    ("„ÒU", "है"),
    ("„ÙU", "हो"),
    ("„Ù", "हो"),
    ("„ıU", "हौ"),
    ("„È°U", "हुँ"),
    ("„ÈU", "हु"),
    ("„È", "हु"),
    ("„ÍU", "हू"),
    ("„Í", "हू"),
    ("„UÊ", "हा"),
    ("„UË", "ही"),
    ("„U", "ह"),
    ("„", "ह"),
    # Combinations for Sha (‡ ... Ê)
    ("‡Ê", "शे"),
    ("‡ÊÒ", "शै"),
    ("‡ÊÙ", "शो"),
    ("‡Êı", "शौ"),
    ("‡ÊÈ", "शु"),
    ("‡ÊÍ", "शू"),
    ("‡ÊÊ", "शा"),
    ("‡ÊË", "शी"),
    ("‡Ê", "श"),
    # Combinations for Shra (ü ... Ê)
    ("üÊË", "श्री"),
    ("üÊ", "श्रे"),
    ("üÊÊ", "श्रा"),
    ("üÊ", "श्र"),
    # Combinations for Gha (ÉÊ)
    ("ÉŸ", "घ्न"),
    ("ÉÊAÊ", "घ्ना"),
    ("ÉÊA", "घ्न"),
    ("ÉÊ", "घे"),
    ("ÉÊÊ", "घा"),
    ("ÉÊ", "घ"),
    # Combinations for Jha (¤Ê)
    ("¤Ê", "झे"),
    ("¤ÊÊ", "झा"),
    ("¤Ê", "झ"),
    # Combinations for Nna (áÊ)
    ("áÊË", "णी"),
    ("áÊÊ", "णा"),
    ("áÊ", "ण"),
    # Combinations for Dha (äÊ)
    ("äÊ", "धे"),
    ("äÊÒ", "धै"),
    ("äÊÙ", "धो"),
    ("äÊı", "धौ"),
    ("äÊÈ", "धु"),
    ("äÊÍ", "धू"),
    ("äÊÊ", "धा"),
    ("äÊË", "धी"),
    ("äÊ", "ध"),
    ("ä", "ध्"),
    # Combinations with Au-matra
    ("ÊÒ", "ौ"),
    # Half Cha (ë) + Chha (¿U) -> च्छ
    ("ë¿U", "च्छ"),
    ("ë¿", "च्छ"),
    ("ë", "च्"),
    # Half Nya (Ü) -> ञ्
    ("Ü", "ञ्"),
    # Conjunct Nna (ÛÊ) -> न्न
    ("ÛÊ", "न्न"),
    ("Û", "न्न्"),
    # Half Ksha (ˇ) before consonant
    ("ˇ◊", "क्ष्म"),
    ("ˇ", "क्ष"),
    # Reph on Rri (´¸§) -> र्ऋ
    ("´¸§", "र्ऋ"),
    # Full Vowel combinations
    ("•Ê", "ओ"),
    ("•ÊÒ", "औ"),
    ("•Ê", "आ"),
    ("•ı", "औ"),
    ("•Ù", "ओ"),
    ("•", "अ"),
    ("ß¸", "ई"),
    ("ß", "इ"),
    ("©U", "उ"),
    ("©", "उ"),
    ("™§", "ऊ"),
    ("´§", "ऋ"),
    ("∞", "ऐ"),
    ("∞", "ए"),
    ("˙", "ॐ"),
    # Complex Conjuncts
    ("c¬", "ष्प"),
    ("TÁ‹", "ञ्जलि"),
    ("◊˜Ô", "म्"),
    ("˜Ô", "्"),
    ("sÔ", "ह्य"),
    ("ˆÔU", "ह्व"),
    ("ˆÔ", "ह्व"),
    ("DÔU", "ष्ठ"),
    ("DÔ", "ष्ठ"),
    ("VÔU", "ङ्के"),
    ("VÔU", "ङ्क"),
    ("XÔU", "ङ्ग"),
    ("XÔ", "ङ्ग"),
    ("OÔU", "ह्रद"),
    ("º˝", "द्र"),
    ("òÊ", "त्र"),
    ("ò", "त्र"),
    ("ˇÊ", "क्ष"),
    ("ˇ", "क्ष"),
    ("ôÊ", "ज्ञ"),
    ("ô", "ज्ञ"),
    ("Çÿ", "ग्य"),
    ("cﬂ", "ष्व"),
    ("p", "श्च"),
    ("l", "द्य"),
    ("m", "द्व"),
    ("…∏U", "ढ़"),
    ("…∏", "ढ़"),
    ("«U", "ड"),
    ("«", "ड"),
    ("∆U", "ठ"),
    ("∆", "ठ"),
    ("¿U", "छ"),
    ("¿", "छ"),
    ("»§", "फ"),
    ("»", "फ"),
    ("M°§", "रूँ"),
    ("M°", "रूँ"),
    ("M§", "रू"),
    ("L§", "रु"),
    ("‚¬%Ë∑§Êÿ", "सपत्नीकाय"),
    ("%", "त्न"),
]

# Single glyph mappings for Chanakya
CHANAKYA_GLYPH_MAP: dict[str, str] = {
    # Consonants
    "π": "ख",
    "ª": "ग",
    "É": "घ",
    "ø": "च",
    "¡": "ज",
    "¤": "झ",
    "≈": "ट",
    "…": "ढ",
    "á": "ण",
    "Ã": "त",
    "Õ": "थ",
    "Œ": "द",
    "œ": "ध",
    "Ÿ": "न",
    "¬": "प",
    "’": "ब",
    "÷": "भ",
    "◊": "म",
    "ÿ": "य",
    "‹": "ल",
    "ﬂ": "व",
    "·": "ष",
    "‚": "स",
    "º": "द",
    "h": "द्ध",
    "N": "हृ",
    "d": "स्र",
    "Q": "क्त",
    "û": "त्त",
    "E": "श्व",
    "j": "द्भ",
    "F": "स्न",
    "e": "द्ग",
    "C": "ष्ट",
    "W": "ङ्ख",
    "K": "्य",
    # Half Consonants (Virama forms)
    "Ä": "क्",
    "Ç": "ग्",
    "Å": "च्",
    "Ö": "ज्",
    "T": "ञ्",
    "à": "त्",
    "â": "थ्",
    "ã": "न्",
    "é": "ब्",
    "c": "ष्",
    "è": "भ्",
    "ê": "म्",
    "S": "स्",
    "‡": "श्",
    "À": "ल्",
    "√": "व्",
    "ü": "श्र्",
    # Matras
    "Ê": "ा",
    "Ë": "ी",
    "È": "ु",
    "Í": "ू",
    "Î": "ृ",
    "": "े",
    "Ò": "ै",
    "Ù": "ो",
    "ı": "ौ",
    "˝": "्र",
    "L": "रु",
    "M": "रू",
    # Modifiers & Punctuation
    "∏": "़",
    "¢": "ं",
    "¥": "ं",
    "°": "ँ",
    "Ú": "ँ",
    "—": "ः",
    "–": "।",
    "H": "॥",
    "˘": "ऽ",
    "˜": "्",
    "ó": "—",
    "Ô": "",
    "U": "",
    "§": "",
}

DEVANAGARI_DIGITS: dict[str, str] = {
    "0": "०",
    "1": "१",
    "2": "२",
    "3": "३",
    "4": "४",
    "5": "५",
    "6": "६",
    "7": "७",
    "8": "८",
    "9": "९",
}

# Precompiled regex patterns for Chanakya reordering
_VIRAMA = "\u094d"
_NUKTA = "\u093c"
_CONS = "[\u0915-\u0939]"
_BASE_CONS = f"(?:{_CONS}{_NUKTA}?)"
_RAKAR = f"(?:{_VIRAMA}\u0930|्र)"
_MATRAS = "[\u093e-\u094c\u0901\u0902]"

_CLUSTER = f"(?:{_BASE_CONS}{_VIRAMA})*{_BASE_CONS}{_RAKAR}?"
_CHHOTI_I_PAT = re.compile(f"Á({_CLUSTER})")
_CHHOTI_I_NASAL_PAT = re.compile(f"®({_CLUSTER})")
_REPH_CHHOTI_I_PAT = re.compile(f"Ì({_CLUSTER})")
_REPH_PAT = re.compile(f"({_CLUSTER})({_MATRAS}*)[¸Z]")


# ==============================================================================
# Nalanda (IAST) Conversion Tables & Constants
# ==============================================================================

NALANDA_PRE_REPLACEMENTS: list[tuple[str, str]] = [
    ("§R", "Ṛ"),
    ("§S", "Ṣ"),
    ("ªU", "Ū"),
    ("µu", "ū"),
    ("°N", "Ṇ"),
    ("ññ", "—"),
    ("›r∂", "Śrī"),
    ("›R∫", "ŚRĪ"),
    ("ëRåmaí", "‘Rāma’"),
    # Convert legacy quotes early so they don't interfere with word-internal letter context
    ("ë", "‘"),
    ("í", "’"),
    ("ì", "“"),
    ("î", "”"),
]

NALANDA_CHAR_MAP: dict[str, str] = {
    # Vowels with diacritics
    "å": "ā",
    "Å": "Ā",
    "∂": "ī",
    "∫": "Ī",
    "µ": "ū",
    "æ": "ṛ",
    # Consonants with diacritics
    "¢": "ṭ",
    "Œ": "ḍ",
    "œ": "Ḍ",
    "ƒ": "ṇ",
    "‹": "ś",
    "›": "Ś",
    "¶": "ṣ",
    "¨": "ḥ",
    "≈": "ṁ",
    "∆": "ṅ",
    "¤": "ñ",
    "Ã": "Ṅ",
    "À": "OM",
    # Nasalization in Awadhi transliteration
    "°": "̃",
    "Ú": "̃",
    # Quotes and dashes
    "ë": "‘",
    "í": "’",
    "ì": "“",
    "î": "”",
    "ó": "—",
    "§": "",
}


# ==============================================================================
# Abstract Font Converter & Implementations
# ==============================================================================


class BaseFontConverter(ABC):
    """Abstract base class for deterministic font encoding converters."""

    @abstractmethod
    def convert(self, text: str) -> str:
        """Convert a text string from legacy encoding to standard Unicode."""
        ...


class ChanakyaConverter(BaseFontConverter):
    """Deterministic converter for Chanakya 8-bit Devanagari encoding."""

    def __init__(self, convert_digits: bool = False) -> None:
        self.convert_digits = convert_digits

    def convert(self, text: str) -> str:
        """Convert raw Chanakya string to Unicode Devanagari.

        Pipeline:
        1. Multi-glyph structural ligature pre-substitution.
        2. Base single-glyph mapping into Devanagari codepoints.
        3. Pre-base Chhoti-I ('Á') cluster reordering past the consonant cluster.
        4. Post-base Reph ('¸' or 'Z') syllable reordering before the consonant cluster.
        5. Virama deduplication and cleanup.
        """
        if not text:
            return ""

        s = text

        # Phase 1: Pre-substitutions of multi-glyph units
        for pattern, repl in CHANAKYA_PRE_REPLACEMENTS:
            s = s.replace(pattern, repl)

        # Phase 2: Convert single glyphs first
        out: list[str] = []
        for c in s:
            if c in ("Á", "®", "Ì", "¸", "Z"):
                out.append(c)
            elif c in CHANAKYA_GLYPH_MAP:
                out.append(CHANAKYA_GLYPH_MAP[c])
            elif self.convert_digits and c in DEVANAGARI_DIGITS:
                out.append(DEVANAGARI_DIGITS[c])
            else:
                out.append(c)
        s = "".join(out)

        # Phase 3: Pre-base Matra Reordering
        # 3a: Standard Chhoti-I ('Á')
        s = _CHHOTI_I_PAT.sub(r"\1ि", s)
        # 3b: Chhoti-I with Anusvara ('®') -> e.g. तब®ह -> तबहिं, ®स -> सिं
        s = _CHHOTI_I_NASAL_PAT.sub(r"\1िं", s)
        # 3c: Combined Reph + Chhoti-I ('Ì') -> e.g. निÌमत -> निर्मित, समर्पि
        s = _REPH_CHHOTI_I_PAT.sub(r"र्\1ि", s)

        # Phase 4: Post-base Reph ('¸' or 'Z') Reordering
        s = _REPH_PAT.sub(r"र्\1\2", s)

        # Phase 5: Cleanups and canonicalizations
        s = s.replace("\u093e\u0947", "\u094b")  # Canonicalize split matra ाे -> ो
        s = s.replace("\u093e\u0948", "\u094c")  # Canonicalize split matra ाै -> ौ
        s = s.replace("््", "्")
        return s


_AWADHI_RETROFLEX_R = re.compile(r"(?<=[a-zå∂µæāīūṛṭḍṇśṣñṅṁ])R")


class NalandaConverter(BaseFontConverter):
    """Deterministic converter for Nalanda 8-bit IAST Roman transliteration encoding."""

    def __init__(self, nasal_as_m: bool = False) -> None:
        self.nasal_as_m = nasal_as_m

    def convert(self, text: str) -> str:
        """Convert raw Nalanda string to standard Unicode IAST."""
        if not text:
            return ""

        s = text
        for pat, repl in NALANDA_PRE_REPLACEMENTS:
            s = s.replace(pat, repl)

        # In Awadhi transliteration, 'R' preceded by a lowercase letter or vowel diacritic
        # represents retroflex flap 'ṛ' (ड़) / 'ṛh' (ढ़), not Latin capital 'R' (as in Rāma)
        s = _AWADHI_RETROFLEX_R.sub("ṛ", s)

        out: list[str] = []
        for c in s:
            if c == "°" and self.nasal_as_m:
                out.append("ṁ")
            elif c in NALANDA_CHAR_MAP:
                out.append(NALANDA_CHAR_MAP[c])
            else:
                out.append(c)
        return "".join(out)


# ==============================================================================
# Legacy Font Normalizer Service
# ==============================================================================

# Regex to strip PDF font subset prefixes (e.g. "KZZLPD+Chanakya" -> "Chanakya")
_SUBSET_PREFIX_REGEX = re.compile(r"^[A-Z]{6}\+")


class LegacyFontNormalizer:
    """Service orchestrating font-aware, span-level normalization of legacy encodings.

    Recognizes embedded font variants such as Chanakya, ChanakyaBold, Nalandatim,
    Nalandahel, and NalandahelBold. Standard or unknown fonts remain untouched.
    """

    def __init__(self) -> None:
        self._converters: dict[str, BaseFontConverter] = {
            "chanakya": ChanakyaConverter(convert_digits=False),
            "nalanda": NalandaConverter(nasal_as_m=False),
        }
        self._matchers: list[tuple[Callable[[str], bool], str]] = [
            (lambda f: "chanakya" in f, "chanakya"),
            (lambda f: "nalanda" in f, "nalanda"),
        ]

    def clean_font_name(self, font_name: str) -> str:
        """Strip PDF 6-character subset prefix (e.g., 'KZZLPD+Chanakya' -> 'Chanakya')."""
        if not font_name:
            return ""
        return _SUBSET_PREFIX_REGEX.sub("", font_name)

    def get_font_family(self, font_name: str) -> str | None:
        """Return canonical legacy font family identifier if recognized, else None."""
        cleaned = self.clean_font_name(font_name).lower()
        for matcher, family in self._matchers:
            if matcher(cleaned):
                return family
        return None

    def is_legacy_font(self, font_name: str) -> bool:
        """Check if font_name belongs to any recognized legacy font family."""
        return self.get_font_family(font_name) is not None

    def normalize_span(
        self,
        text: str,
        font_name: str,
        is_transliteration: bool = False,
    ) -> tuple[str, bool, str | None]:
        """Normalize a single text span based on its specific font name.

        Args:
            text: Raw span text as extracted by PyMuPDF.
            font_name: Font name associated with the span.
            is_transliteration: Whether this span appears in a transliteration
                context (e.g. adjacent to Nalanda text). If True, isolated borrowed
                nasal glyphs ('°', 'Ú') are converted to Roman combining tilde (\\u0303).

        Returns:
            A tuple of (normalized_text, was_converted, matched_family).
            If font is not recognized or text is unchanged, was_converted is False.
        """
        if not text:
            return text, False, None

        family = self.get_font_family(font_name)

        # Context-aware borrowed nasal glyphs:
        # Typesetters borrowed zero-width ChanakyaBold glyphs '°' and 'Ú' into Roman
        # transliteration lines. In transliteration context, these must become Roman
        # combining tilde (\u0303), not Devanagari candrabindu (ँ) or literal 'Ú'.
        if is_transliteration and ("°" in text or "Ú" in text):
            if re.match(r"^[\s]*[°Ú][\s,\.]*$", text):
                converted = text.replace("°", "\u0303").replace("Ú", "\u0303")
                return converted, True, "nalanda"

        if family is None or family not in self._converters:
            return text, False, None

        converter = self._converters[family]
        converted = converter.convert(text)
        was_converted = converted != text
        return converted, was_converted, family

    def register_converter(
        self,
        family_name: str,
        matcher: Callable[[str], bool],
        converter: BaseFontConverter,
    ) -> None:
        """Register a new font family converter for future extensibility."""
        self._converters[family_name.lower()] = converter
        self._matchers.append((matcher, family_name.lower()))
