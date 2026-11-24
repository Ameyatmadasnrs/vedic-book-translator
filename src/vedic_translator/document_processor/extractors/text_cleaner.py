"""Text sanitization and artifact removal service for Vedic and scripture documents.

Eliminates OCR and layout artifacts, metrical marker prefixes (e.g. 'दो०—', 'चौ०—',
'दो0ó'), trailing page numbers, and typographic spacing irregularities from
extracted verse text and transliterations prior to translation.
"""

import re

# Metrical marker prefixes in Devanagari script
DEV_METRICAL_PREFIX_REGEX = re.compile(
    r"^(?:दो[०0][—ó\-]|चौ[०0][—ó\-]|छं[०0][—ó\-]|सो[०0][—ó\-]|"
    r"दो[०0]|चौ[०0]|छं[०0]|सो[०0]|"
    r"श्लोक\s*[:—\-]?|दोहा\s*[:—\-]?|चौपाई\s*[:—\-]?|सोरठा\s*[:—\-]?|छन्द\s*[:—\-]?)\s*"
)

# Metrical marker prefixes in IAST transliteration (e.g., "Cau.: ", "Do.: ", "Chaṁ.: ")
IAST_METRICAL_PREFIX_REGEX = re.compile(
    r"^(?:Do\.|Cau\.|So\.|Chh\.|Sloka|Chaṁ\.)\s*:\s*", re.IGNORECASE
)

# Trailing page numbers (e.g., " 216", " 217", " 218") at the end of transliteration lines
TRAILING_PAGE_NUM_REGEX = re.compile(r"\s+\d{1,4}\s*$")

# Multiple horizontal whitespace characters (spaces/tabs)
HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[ \t]{2,}")

# Whitespace surrounding linebreaks
LINEBREAK_WHITESPACE_REGEX = re.compile(r"[ \t]*\n[ \t]*")


def sanitize_verse_text(text: str) -> str:
    """Sanitize Devanagari verse text for consumption by the translation engine.

    Performs:
    1. Removal of metrical marker headings/prefixes (e.g., 'दो०—', 'चौ०—', 'दो0ó').
    2. Normalization of intra-line multiple spaces into single spaces.
    3. Normalization of broken linebreaks into single spaces or clean newlines.
    4. Trimming of leading/trailing whitespace.

    Args:
        text: Raw extracted original verse text.

    Returns:
        Cleaned, natural verse poetry string.
    """
    if not text:
        return ""

    s = text.strip()
    s = DEV_METRICAL_PREFIX_REGEX.sub("", s)
    s = HORIZONTAL_WHITESPACE_REGEX.sub(" ", s)
    s = LINEBREAK_WHITESPACE_REGEX.sub(" ", s)
    return s.strip()


def sanitize_transliteration(text: str) -> str:
    """Sanitize IAST Roman transliteration for consumption by the translation engine.

    Performs:
    1. Removal of transliteration metrical marker prefixes (e.g., 'Do.: ', 'Cau.: ').
    2. Stripping of trailing page numbers (e.g., ' 217', ' 218').
    3. Normalization of multiple horizontal spaces and linebreaks.
    4. Trimming of leading/trailing whitespace.

    Args:
        text: Raw extracted transliteration text.

    Returns:
        Cleaned IAST transliteration string.
    """
    if not text:
        return ""

    s = text.strip()
    s = IAST_METRICAL_PREFIX_REGEX.sub("", s)
    s = TRAILING_PAGE_NUM_REGEX.sub("", s)
    s = HORIZONTAL_WHITESPACE_REGEX.sub(" ", s)
    s = LINEBREAK_WHITESPACE_REGEX.sub(" ", s)
    return s.strip()


def sanitize_translation(text: str) -> str:
    """Sanitize secondary English reference translation.

    Normalizes multiple horizontal spaces while preserving logical paragraph flow.

    Args:
        text: Raw extracted English translation reference.

    Returns:
        Cleaned English reference text.
    """
    if not text:
        return ""

    s = text.strip()
    s = HORIZONTAL_WHITESPACE_REGEX.sub(" ", s)
    return s.strip()
