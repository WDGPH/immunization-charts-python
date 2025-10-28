"""Unit tests for enums module - batch strategy, language, and template field enumerations.

Tests cover:
- BatchStrategy enum values and string conversion
- BatchType enum values and strategy mapping
- Language enum values and string conversion
- TemplateField enum values and field availability
- Error handling for invalid values
- Case-insensitive conversion
- Default behavior for None values

Real-world significance:
- Batch strategy determines how PDFs are grouped (by size, school, board)
- Language code determines template renderer and localization
- Template fields define available placeholders for QR codes and PDF passwords
- Invalid values would cause pipeline crashes or incorrect behavior
"""

from __future__ import annotations

import pytest

from pipeline.enums import BatchStrategy, BatchType, Language, TemplateField


@pytest.mark.unit
class TestBatchStrategy:
    """Unit tests for BatchStrategy enumeration."""

    def test_enum_values_correct(self) -> None:
        """Verify BatchStrategy has expected enum values.

        Real-world significance:
        - Defines valid batching strategies for pipeline
        """
        assert BatchStrategy.SIZE.value == "size"
        assert BatchStrategy.SCHOOL.value == "school"
        assert BatchStrategy.BOARD.value == "board"

    def test_from_string_valid_lowercase(self) -> None:
        """Verify from_string works with lowercase input.

        Real-world significance:
        - Config values are often lowercase in YAML
        """
        assert BatchStrategy.from_string("size") == BatchStrategy.SIZE
        assert BatchStrategy.from_string("school") == BatchStrategy.SCHOOL
        assert BatchStrategy.from_string("board") == BatchStrategy.BOARD

    def test_from_string_valid_uppercase(self) -> None:
        """Verify from_string is case-insensitive for uppercase.

        Real-world significance:
        - Users might input "SIZE" or "BOARD" in config
        """
        assert BatchStrategy.from_string("SIZE") == BatchStrategy.SIZE
        assert BatchStrategy.from_string("SCHOOL") == BatchStrategy.SCHOOL
        assert BatchStrategy.from_string("BOARD") == BatchStrategy.BOARD

    def test_from_string_valid_mixed_case(self) -> None:
        """Verify from_string is case-insensitive for mixed case.

        Real-world significance:
        - Should accept any case variation
        """
        assert BatchStrategy.from_string("Size") == BatchStrategy.SIZE
        assert BatchStrategy.from_string("School") == BatchStrategy.SCHOOL
        assert BatchStrategy.from_string("BoArD") == BatchStrategy.BOARD

    def test_from_string_none_defaults_to_size(self) -> None:
        """Verify None defaults to SIZE strategy.

        Real-world significance:
        - Missing batching config should use safe default (SIZE)
        """
        assert BatchStrategy.from_string(None) == BatchStrategy.SIZE

    def test_from_string_invalid_value_raises_error(self) -> None:
        """Verify ValueError for invalid strategy string.

        Real-world significance:
        - User error (typo in config) must be caught and reported clearly
        """
        with pytest.raises(ValueError, match="Unknown batch strategy: invalid"):
            BatchStrategy.from_string("invalid")

    def test_from_string_invalid_error_includes_valid_options(self) -> None:
        """Verify error message includes list of valid options.

        Real-world significance:
        - Users need to know what values are valid when they make a mistake
        """
        with pytest.raises(ValueError) as exc_info:
            BatchStrategy.from_string("bad")

        error_msg = str(exc_info.value)
        assert "size" in error_msg
        assert "school" in error_msg
        assert "board" in error_msg


@pytest.mark.unit
class TestBatchType:
    """Unit tests for BatchType enumeration."""

    def test_enum_values_correct(self) -> None:
        """Verify BatchType has expected enum values.

        Real-world significance:
        - Type descriptors used for batch metadata and reporting
        """
        assert BatchType.SIZE_BASED.value == "size_based"
        assert BatchType.SCHOOL_GROUPED.value == "school_grouped"
        assert BatchType.BOARD_GROUPED.value == "board_grouped"


@pytest.mark.unit
class TestStrategyTypeIntegration:
    """Integration tests between BatchStrategy and BatchType."""

    def test_all_strategies_round_trip(self) -> None:
        """Verify strategies convert to/from string consistently.

        Real-world significance:
        - Required for config persistence and reproducibility
        """
        for strategy in BatchStrategy:
            string_value = strategy.value
            reconstructed = BatchStrategy.from_string(string_value)
            assert reconstructed == strategy


@pytest.mark.unit
class TestLanguage:
    """Unit tests for Language enumeration."""

    def test_enum_values_correct(self) -> None:
        """Verify Language enum has correct values.

        Real-world significance:
        - Defines supported output languages for immunization notices
        """
        assert Language.ENGLISH.value == "en"
        assert Language.FRENCH.value == "fr"

    def test_language_from_string_english(self) -> None:
        """Verify from_string('en') returns ENGLISH.

        Real-world significance:
        - CLI and config often pass language as lowercase strings
        """
        assert Language.from_string("en") == Language.ENGLISH

    def test_language_from_string_french(self) -> None:
        """Verify from_string('fr') returns FRENCH.

        Real-world significance:
        - CLI and config often pass language as lowercase strings
        """
        assert Language.from_string("fr") == Language.FRENCH

    def test_language_from_string_case_insensitive_english(self) -> None:
        """Verify from_string() is case-insensitive for English.

        Real-world significance:
        - Users might input 'EN', 'En', etc.; should accept any case
        """
        assert Language.from_string("EN") == Language.ENGLISH
        assert Language.from_string("En") == Language.ENGLISH

    def test_language_from_string_case_insensitive_french(self) -> None:
        """Verify from_string() is case-insensitive for French.

        Real-world significance:
        - Users might input 'FR', 'Fr', etc.; should accept any case
        """
        assert Language.from_string("FR") == Language.FRENCH
        assert Language.from_string("Fr") == Language.FRENCH

    def test_language_from_string_none_defaults_to_english(self) -> None:
        """Verify from_string(None) defaults to ENGLISH.

        Real-world significance:
        - Allows safe default language when none specified in config
        """
        assert Language.from_string(None) == Language.ENGLISH

    def test_language_from_string_invalid_raises_error(self) -> None:
        """Verify from_string() raises ValueError for unsupported language.

        Real-world significance:
        - User error (typo in config or CLI) must be caught and reported clearly
        """
        with pytest.raises(ValueError, match="Unsupported language: es"):
            Language.from_string("es")

    def test_language_from_string_error_includes_valid_options(self) -> None:
        """Verify error message includes list of valid language options.

        Real-world significance:
        - Users need to know what language codes are valid when they make a mistake
        """
        with pytest.raises(ValueError) as exc_info:
            Language.from_string("xyz")

        error_msg = str(exc_info.value)
        assert "Valid options:" in error_msg
        assert "en" in error_msg
        assert "fr" in error_msg

    def test_language_all_codes(self) -> None:
        """Verify all_codes() returns set of all language codes.

        Real-world significance:
        - CLI argument parser and config validation use this to determine
          allowed language choices
        """
        assert Language.all_codes() == {"en", "fr"}

    def test_language_all_codes_returns_set(self) -> None:
        """Verify all_codes() returns a set (not list or tuple).

        Real-world significance:
        - argparse.choices expects a container; set is optimal for O(1) lookups
        """
        codes = Language.all_codes()
        assert isinstance(codes, set)
        assert len(codes) == 2

    def test_language_from_string_round_trip(self) -> None:
        """Verify languages convert to/from string consistently.

        Real-world significance:
        - Required for config persistence and reproducibility
        """
        for lang in Language:
            string_value = lang.value
            reconstructed = Language.from_string(string_value)
            assert reconstructed == lang


@pytest.mark.unit
class TestTemplateField:
    """Unit tests for TemplateField enumeration."""

    def test_enum_values_correct(self) -> None:
        """Verify TemplateField has expected enum values.

        Real-world significance:
        - Defines available placeholders for template rendering in QR codes
          and PDF password generation
        """
        assert TemplateField.CLIENT_ID.value == "client_id"
        assert TemplateField.FIRST_NAME.value == "first_name"
        assert TemplateField.LAST_NAME.value == "last_name"
        assert TemplateField.NAME.value == "name"
        assert TemplateField.DATE_OF_BIRTH.value == "date_of_birth"
        assert TemplateField.DATE_OF_BIRTH_ISO.value == "date_of_birth_iso"
        assert (
            TemplateField.DATE_OF_BIRTH_ISO_COMPACT.value == "date_of_birth_iso_compact"
        )
        assert TemplateField.SCHOOL.value == "school"
        assert TemplateField.BOARD.value == "board"
        assert TemplateField.STREET_ADDRESS.value == "street_address"
        assert TemplateField.CITY.value == "city"
        assert TemplateField.PROVINCE.value == "province"
        assert TemplateField.POSTAL_CODE.value == "postal_code"
        assert TemplateField.LANGUAGE_CODE.value == "language_code"

    def test_template_field_enum_has_all_fields(self) -> None:
        """Verify TemplateField enum contains all expected fields.

        Real-world significance:
        - Ensures all client context fields are available for templating
        - Any missing field would cause template validation errors
        """
        expected = {
            "client_id",
            "first_name",
            "last_name",
            "name",
            "date_of_birth",
            "date_of_birth_iso",
            "date_of_birth_iso_compact",
            "school",
            "board",
            "street_address",
            "city",
            "province",
            "postal_code",
            "language_code",
        }
        assert TemplateField.all_values() == expected

    def test_template_field_all_values_returns_set(self) -> None:
        """Verify all_values() returns a set for use with set operations.

        Real-world significance:
        - Set operations needed for validation (set difference to find disallowed fields)
        """
        values = TemplateField.all_values()
        assert isinstance(values, set)
        assert len(values) == 14

    def test_template_field_count_matches_enum(self) -> None:
        """Verify number of fields matches enum member count.

        Real-world significance:
        - Prevents accidental field additions being missed in all_values()
        """
        enum_members = [f for f in TemplateField]
        all_values = TemplateField.all_values()
        assert len(enum_members) == len(all_values)

    def test_template_field_includes_board(self) -> None:
        """Verify TemplateField includes 'board' field (was missing from old QR whitelist).

        Real-world significance:
        - board field is generated by build_client_context() but was not
          included in SUPPORTED_QR_TEMPLATE_FIELDS, causing inconsistency
        """
        assert "board" in TemplateField.all_values()
        assert TemplateField.BOARD.value == "board"
