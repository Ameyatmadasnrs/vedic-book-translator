"""Unit tests for LegacyFontNormalizer, ChanakyaConverter, and NalandaConverter."""

import pytest

from vedic_translator.document_processor.extractors.font_normalizer import (
    ChanakyaConverter,
    LegacyFontNormalizer,
    NalandaConverter,
)


class TestChanakyaConverter:
    """Tests for Chanakya 8-bit Devanagari converter."""

    @pytest.fixture
    def converter(self) -> ChanakyaConverter:
        return ChanakyaConverter()

    def test_empty_string(self, converter: ChanakyaConverter) -> None:
        assert converter.convert("") == ""

    def test_tvameva_prayer_conversion(self, converter: ChanakyaConverter) -> None:
        # Page 2 Sanskrit prayer
        assert converter.convert("àﬂ◊ﬂ ◊ÊÃÊ ø Á¬ÃÊ àﬂ◊ﬂ") == "त्वमेव माता च पिता त्वमेव"
        assert converter.convert("àﬂ◊ﬂ ’ãäÊÈ‡ø ‚πÊ àﬂ◊ﬂ–") == "त्वमेव बन्धुश्च सखा त्वमेव।"
        assert converter.convert("àﬂ◊ﬂ ÁﬂlÊ º˝ÁﬂáÊ¢ àﬂ◊ﬂ") == "त्वमेव विद्या द्रविणं त्वमेव"
        assert converter.convert("àﬂ◊ﬂ ‚ﬂZ ◊◊ ŒﬂŒﬂH") == "त्वमेव सर्व मम देवदेव॥"

    def test_pre_base_matra_reordering(self, converter: ChanakyaConverter) -> None:
        # 'Á' must move past single consonants, conjuncts, and clusters
        assert converter.convert("Á¬ÃÊ") == "पिता"
        assert converter.convert("ÁﬂlÊ") == "विद्या"
        assert converter.convert("Á¬˝ÿ") == "प्रिय"
        assert converter.convert("Á’ŸËÃ") == "बिनीत"
        assert converter.convert("ÁòÊ÷ÈﬂŸ") == "त्रिभुवन"

    def test_post_base_reph_reordering(self, converter: ChanakyaConverter) -> None:
        # '¸' or 'Z' must move before the entire syllable cluster
        assert converter.convert("‚ﬂZ") == "सर्व"
        assert converter.convert("‚ﬂ¸") == "सर्व"
        assert converter.convert("‚ﬂÊ¸") == "सर्वा"
        assert converter.convert("‚ﬂÊ¸Áœ¬—") == "सर्वाधिपः"

    def test_complex_conjuncts(self, converter: ChanakyaConverter) -> None:
        assert converter.convert("VÔU") == "ङ्क"
        assert converter.convert("XÔU") == "ङ्ग"
        assert converter.convert("l") == "द्य"
        assert converter.convert("m") == "द्व"
        assert converter.convert("DÔU") == "ष्ठ"
        assert converter.convert("sÔ") == "ह्य"
        assert converter.convert("ë¿U") == "च्छ"
        assert converter.convert("ÛÊ") == "न्न"
        assert converter.convert("Ü") == "ञ्"
        assert converter.convert("ŒÎ…∏U") == "दृढ़"

    def test_doha_188_conversion(self, converter: ChanakyaConverter) -> None:
        raw = "∑§ı‚ÀÿÊÁŒ ŸÊÁ⁄U Á¬˝ÿ ‚’ •Êø⁄UŸ ¬ÈŸËÃ–"
        expected = "कौसल्यादि नारि प्रिय सब आचरन पुनीत।"
        assert converter.convert(raw) == expected

    def test_audit_conjunct_corrections(self, converter: ChanakyaConverter) -> None:
        # Regression tests for all conjuncts and glyphs fixed from quality audit
        test_cases = [
            ("ÁﬂcáÊÈ", "विष्णु"),
            ("⁄UQ§", "रक्त"),
            ("Á‚Áh", "सिद्धि"),
            ("NUŒÿ", "हृदय"),
            ("©UûÊ⁄U", "उत्तर"),
            ("’«∏\uf8ffU", "बड़े"),
            ("’…∏KÙ", "बढ़्यो"),
            ("Á‚hKÕZ", "सिद्धयर्थ"),
            ("◊„\uf8ffUE⁄U", "महेश्वर"),
            ("¬˝F", "प्रस्न"),
            ("•FÊŸÊ", "अस्नाना"),
            ("¡ªeÈL¢§", "जगद्गुरुं"),
            ("‡ÊWÔ", "शङ्ख"),
            ("¬˝tÔUÊŒ", "प्रह्लाद"),
            ("ÁøqÔ¢U", "चिह्नं"),
            ("Sﬂ¬A", "स्वप्न"),
            ("∑§CÔU", "कष्ट"),
            ("ŸÊßZ", "नाईं"),
            ("‡‹Ê\uf8ff∑§", "श्लोक"),
            ("‚„Ud", "सहस्र"),
            ("ŒûÊ¢", "दत्तं"),
            ("©Ujﬂ", "उद्भव"),
            ("◊Èe⁄U", "मुद्गर"),
            ("÷ÁQ§—", "भक्तिः"),
        ]
        for raw, expected in test_cases:
            assert converter.convert(raw) == expected, f"Failed converting {raw} to {expected}"

    def test_split_matra_canonicalization(self, converter: ChanakyaConverter) -> None:
        # In Chanakya, decomposed Aa-matra + E-matra must resolve to unified O-matra
        assert converter.convert("∑§Ê") == "को"
        assert converter.convert("∑§Ê\uf8ff") == "को"
        assert converter.convert("∑§ÊÒ") == "कौ"

    def test_metrical_marker_ligatures(self, converter: ChanakyaConverter) -> None:
        # Chanakya 8-bit meter prefixes must resolve to Devanagari abbreviation + em-dash
        assert converter.convert("ŒÙ0ó") == "दो०—"
        assert converter.convert("øı0ó") == "चौ०—"
        assert converter.convert("¿¢U0ó") == "छं०—"
        assert converter.convert("‚Ù0ó") == "सो०—"

    def test_pre_base_chhoti_i_with_anusvara(self, converter: ChanakyaConverter) -> None:
        # Glyph '®' (0xAE) represents pre-base Chhoti-I with Anusvara (िं)
        assert converter.convert("Ã’®„U") == "तबहिं"
        assert converter.convert("¬ÈL§·®‚„U") == "पुरुषसिंह"
        assert converter.convert("∑Î§¬Ê®‚œÈ") == "कृपासिंधु"
        assert converter.convert("ÁøÃﬂ®„U") == "चितवहिं"
        assert converter.convert("’Ëø®„U") == "बीचहिं"
        assert converter.convert("Ÿ®„U") == "नहिं"
        assert converter.convert("∞∑§®„U") == "एकहिं"
        assert converter.convert("‚⁄UŸ®„U") == "सरनहिं"

    def test_pre_base_reph_with_chhoti_i(self, converter: ChanakyaConverter) -> None:
        # Glyph 'Ì' (0xCC) represents combined pre-base Reph + Chhoti-I (र्...ि)
        assert converter.convert("Á’Áœ ÁŸÌ◊Ã") == "बिधि निर्मित"
        assert converter.convert("•ÊÿÈœ ‚’¸ ‚◊Ì¬") == "आयुध सर्ब समर्पि"
        assert (
            converter.convert("’˝rÊÔÊ¢«U ÁŸ∑§ÊÿÊ ÁŸÌ◊Ã ◊ÊÿÊ ⁄UÙ◊ ⁄UÙ◊ ¬˝ÁÃ ’\uf8ffŒ ∑§„ÒU–")
            == "ब्रह्मांड निकाया निर्मित माया रोम रोम प्रति बेद कहै।"
        )

    def test_sravahi_regression(self, converter: ChanakyaConverter) -> None:
        # Raw Chanakya sequence 'dﬂÁ„U¢U' on page 217 must produce 'स्रवहिं', not 'स्र्वहिं'
        assert converter.convert("dﬂÁ„U¢U") == "स्रवहिं"
        assert converter.convert("dﬂ") == "स्रव"


class TestNalandaConverter:
    """Tests for Nalanda IAST Roman transliteration converter."""

    @pytest.fixture
    def converter(self) -> NalandaConverter:
        return NalandaConverter()

    def test_empty_string(self, converter: NalandaConverter) -> None:
        assert converter.convert("") == ""

    def test_basic_diacritics(self, converter: NalandaConverter) -> None:
        assert converter.convert("Råma") == "Rāma"
        assert converter.convert("›r∂") == "Śrī"
        assert converter.convert("S∂tå") == "Sītā"
        assert converter.convert("hædaya") == "hṛdaya"
        assert converter.convert("Pu¶pa") == "Puṣpa"
        assert converter.convert("Lak¶maƒa") == "Lakṣmaṇa"

    def test_macron_u_ligature(self, converter: NalandaConverter) -> None:
        # 'µu' combination -> 'ū'
        assert converter.convert("Dhµupa") == "Dhūpa"
        assert converter.convert("Tåmbµula") == "Tāmbūla"
        assert converter.convert("Åbhµu¶aƒa") == "Ābhūṣaṇa"

    def test_retroflex_and_heading_caps(self, converter: NalandaConverter) -> None:
        assert converter.convert("Kåkabhu‹uƒŒi") == "Kākabhuśuṇḍi"
        assert converter.convert("BÅLA-KÅ°NœA") == "BĀLA-KĀṆḌA"
        assert converter.convert("AYODHYÅ-KÅ°NœA") == "AYODHYĀ-KĀṆḌA"

    def test_quotes_and_dashes(self, converter: NalandaConverter) -> None:
        assert converter.convert("ìObeisanceî") == "“Obeisance”"
        assert converter.convert("ëRåmaí") == "‘Rāma’"
        assert converter.convert("follows:ó") == "follows:—"
        assert converter.convert("wombññthis") == "womb—this"

    def test_uppercase_diacritics(self, converter: NalandaConverter) -> None:
        assert converter.convert("§R¶i") == "Ṛṣi"
        assert converter.convert("ªUrdhvarekhå") == "Ūrdhvarekhā"

    def test_awadhi_retroflex_r(self, converter: NalandaConverter) -> None:
        assert converter.convert("baRa") == "baṛa"
        assert converter.convert("dæRha") == "dṛṛha"
        assert converter.convert("caRhi") == "caṛhi"
        assert converter.convert("baRappanu") == "baṛappanu"

    def test_genuine_capital_r_preserved(self, converter: NalandaConverter) -> None:
        assert converter.convert("Råma") == "Rāma"
        assert converter.convert("‘Råma’") == "‘Rāma’"
        assert converter.convert("“Råma”") == "“Rāma”"
        assert converter.convert("Śrī Rāma") == "Śrī Rāma"


class TestLegacyFontNormalizer:
    """Tests for LegacyFontNormalizer service."""

    @pytest.fixture
    def normalizer(self) -> LegacyFontNormalizer:
        return LegacyFontNormalizer()

    def test_clean_font_name_with_subset(self, normalizer: LegacyFontNormalizer) -> None:
        assert normalizer.clean_font_name("KZZLPD+Chanakya") == "Chanakya"
        assert normalizer.clean_font_name("QAYTYV+ChanakyaBold") == "ChanakyaBold"
        assert normalizer.clean_font_name("BAYRND+NalandahelBold") == "NalandahelBold"
        assert normalizer.clean_font_name("Times-Roman") == "Times-Roman"
        assert normalizer.clean_font_name("") == ""

    def test_get_font_family(self, normalizer: LegacyFontNormalizer) -> None:
        assert normalizer.get_font_family("KZZLPD+Chanakya") == "chanakya"
        assert normalizer.get_font_family("QAYTYV+ChanakyaBold") == "chanakya"
        assert normalizer.get_font_family("UCJDBY+Nalandatim") == "nalanda"
        assert normalizer.get_font_family("BAYRND+NalandahelBold") == "nalanda"
        assert normalizer.get_font_family("Times-Roman") is None
        assert normalizer.get_font_family("Arial") is None

    def test_normalize_span_chanakya(self, normalizer: LegacyFontNormalizer) -> None:
        text, converted, family = normalizer.normalize_span("àﬂ◊ﬂ", "KZZLPD+Chanakya")
        assert text == "त्वमेव"
        assert converted is True
        assert family == "chanakya"

    def test_normalize_span_nalanda(self, normalizer: LegacyFontNormalizer) -> None:
        text, converted, family = normalizer.normalize_span("›r∂ Råma", "UCJDBY+Nalandatim")
        assert text == "Śrī Rāma"
        assert converted is True
        assert family == "nalanda"

    def test_normalize_span_standard_font_untouched(self, normalizer: LegacyFontNormalizer) -> None:
        raw = "Then water should be sipped thrice."
        text, converted, family = normalizer.normalize_span(raw, "Times-Roman")
        assert text == raw
        assert converted is False
        assert family is None

    def test_normalize_span_empty(self, normalizer: LegacyFontNormalizer) -> None:
        text, converted, family = normalizer.normalize_span("", "Chanakya")
        assert text == ""
        assert converted is False
        assert family is None

    def test_context_aware_nasal_marks(self, normalizer: LegacyFontNormalizer) -> None:
        # In transliteration context, borrowed zero-width Chanakya nasal marks
        # must become Roman combining tilde (\u0303)
        text, converted, family = normalizer.normalize_span(
            "°", "ChanakyaBold", is_transliteration=True
        )
        assert text == "\u0303"
        assert converted is True
        assert family == "nalanda"

        text, converted, family = normalizer.normalize_span(
            "Ú", "ChanakyaBold", is_transliteration=True
        )
        assert text == "\u0303"
        assert converted is True
        assert family == "nalanda"

        # Trailing space or punctuation preserved
        text, converted, family = normalizer.normalize_span(
            "° ", "ChanakyaBold", is_transliteration=True
        )
        assert text == "\u0303 "

        text, converted, family = normalizer.normalize_span(
            "Ú,", "ChanakyaBold", is_transliteration=True
        )
        assert text == "\u0303,"

        # In Devanagari context (is_transliteration=False), Chanakya ° converts to candrabindu
        text, converted, family = normalizer.normalize_span(
            "°", "ChanakyaBold", is_transliteration=False
        )
        assert text == "ँ"
        assert converted is True
        assert family == "chanakya"

        # Multi-character Devanagari words in translit lines are still converted as Devanagari
        text, converted, family = normalizer.normalize_span(
            "∑Î§¬Ê°", "ChanakyaBold", is_transliteration=True
        )
        assert text == "कृपाँ"
        assert converted is True
        assert family == "chanakya"
