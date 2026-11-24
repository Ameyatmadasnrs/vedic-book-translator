"""Unit tests for verse and transliteration text sanitization."""

from vedic_translator.document_processor.extractors.text_cleaner import (
    sanitize_translation,
    sanitize_transliteration,
    sanitize_verse_text,
)


class TestTextCleaner:
    """Tests for text sanitization functions."""

    def test_sanitize_verse_text_empty(self) -> None:
        assert sanitize_verse_text("") == ""
        assert sanitize_verse_text("   ") == ""

    def test_sanitize_verse_text_meter_prefixes(self) -> None:
        # Standard normalized Gita Press forms
        assert (
            sanitize_verse_text("दो०—तब अदृस्य भए पावक सकल सभहि समुझाइ।")
            == "तब अदृस्य भए पावक सकल सभहि समुझाइ।"
        )
        assert sanitize_verse_text("चौ०—तबहिं रायँ प्रिय नारि बोलाईं।") == "तबहिं रायँ प्रिय नारि बोलाईं।"
        assert (
            sanitize_verse_text("छं०—भए प्रगट कृपाला दीनदयाला कौसल्या हितकारी।")
            == "भए प्रगट कृपाला दीनदयाला कौसल्या हितकारी।"
        )
        assert sanitize_verse_text("सो०—जेहि सुमिरत सिधि होइ") == "जेहि सुमिरत सिधि होइ"

        # Legacy font conversion forms (दो0ó, चौ0ó)
        assert sanitize_verse_text("दो0ó कौसल्यादि बिदित सब रीती।") == "कौसल्यादि बिदित सब रीती।"
        assert sanitize_verse_text("चौ0ó एक बार भूपति मन माहीं।") == "एक बार भूपति मन माहीं।"
        assert sanitize_verse_text("छं0ó भए प्रगट कृपाला") == "भए प्रगट कृपाला"

        # Bare abbreviation prefixes
        assert sanitize_verse_text("दो० जोग लगन ग्रह बार तिथि") == "जोग लगन ग्रह बार तिथि"
        assert sanitize_verse_text("चौ० नौमी तिथि मधु मास") == "नौमी तिथि मधु मास"

    def test_sanitize_verse_text_whitespace(self) -> None:
        raw = "चौ०—तबहिं    रायँ    प्रिय   नारि\nबोलाईं। कौसल्यादि \nतहाँ \nचलि \nआईं॥"
        expected = "तबहिं रायँ प्रिय नारि बोलाईं। कौसल्यादि तहाँ चलि आईं॥"
        assert sanitize_verse_text(raw) == expected

    def test_sanitize_transliteration_empty(self) -> None:
        assert sanitize_transliteration("") == ""
        assert sanitize_transliteration("   ") == ""

    def test_sanitize_transliteration_meter_prefixes(self) -> None:
        assert (
            sanitize_transliteration("Do.: taba adṛsya bhae pāvaka sakala")
            == "taba adṛsya bhae pāvaka sakala"
        )
        assert sanitize_transliteration("Cau.: tabahĩ rāyã priya nāri") == "tabahĩ rāyã priya nāri"
        assert (
            sanitize_transliteration("Chaṁ.:bhae pragaṭa kṛpālā dīnadayālā")
            == "bhae pragaṭa kṛpālā dīnadayālā"
        )
        assert sanitize_transliteration("So.: jehi sumirata sidhi hoi") == "jehi sumirata sidhi hoi"

    def test_sanitize_transliteration_trailing_page_numbers(self) -> None:
        assert (
            sanitize_transliteration("Do.: Kausalyādi bidita saba rītī... 216")
            == "Kausalyādi bidita saba rītī..."
        )
        assert (
            sanitize_transliteration("Do.: cara aru acara harṣajuta rāma janama sukhamūla.190. 217")
            == "cara aru acara harṣajuta rāma janama sukhamūla.190."
        )
        assert (
            sanitize_transliteration("jaganivāsa prabhu pragaṭe akhila loka biśrāma.191. 218")
            == "jaganivāsa prabhu pragaṭe akhila loka biśrāma.191."
        )

    def test_sanitize_translation(self) -> None:
        raw = "The king at once    sent for   his beloved consorts."
        expected = "The king at once sent for his beloved consorts."
        assert sanitize_translation(raw) == expected
        assert sanitize_translation("") == ""
