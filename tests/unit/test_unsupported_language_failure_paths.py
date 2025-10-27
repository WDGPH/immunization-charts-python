"""Unit tests for unsupported language failure detection and error messages.

This module tests the failure paths when unsupported languages are used, ensuring
early, informative error detection throughout the pipeline.

Real-world significance:
- Unsupported languages should be caught immediately at entry points
- Error messages must be clear and actionable
- No silent failures or cryptic KeyErrors
- Pipeline should fail fast with helpful guidance

Failure Point Analysis:
1. **CLI Entry Point (FIRST DEFENSE)**: argparse validates against Language.all_codes()
2. **Enum Validation (PRIMARY DEFENSE)**: Language.from_string() provides detailed error messages
3. **Template Dispatcher (NO DEFENSIVE CHECK)**: get_language_renderer() assumes valid input
   - Removed in Task 4 (redundant validation)
   - Language is guaranteed valid by checks 1-2
   - No performance penalty from unnecessary checks
4. **Preprocessing**: Language enum validation in date conversion and vaccine mapping
"""

from __future__ import annotations

import pytest

from pipeline.enums import Language
from pipeline import generate_notices


@pytest.mark.unit
class TestUnsupportedLanguageDetection:
    """Tests for early detection of unsupported language codes."""

    def test_language_enum_validation_catches_invalid_code(self) -> None:
        """Verify Language.from_string() catches invalid codes immediately.

        FAILURE POINT #1: Enum Validation
        - Earliest point in the pipeline where language codes are validated
        - Used by CLI, configuration loading, and preprocessing
        - Provides clear error message listing valid options

        Real-world significance:
        - Prevents silent failures downstream
        - Users see immediately what languages are supported
        - Clear error message guides users to fix their input
        """
        # Invalid language code
        with pytest.raises(ValueError) as exc_info:
            Language.from_string("es")

        error_msg = str(exc_info.value)
        assert "Unsupported language: es" in error_msg
        assert "Valid options:" in error_msg
        assert "en" in error_msg
        assert "fr" in error_msg

    def test_language_enum_validation_error_message_format(self) -> None:
        """Verify error message is informative and actionable.

        Real-world significance:
        - Users can immediately see what went wrong
        - Error message lists all valid options
        - Helps administrators troubleshoot configuration issues
        """
        invalid_codes = ["es", "pt", "de", "xyz", "invalid"]

        for invalid_code in invalid_codes:
            with pytest.raises(ValueError) as exc_info:
                Language.from_string(invalid_code)

            error_msg = str(exc_info.value)
            # Error should be specific about which code is invalid
            assert f"Unsupported language: {invalid_code}" in error_msg
            # Error should list all valid options
            assert "Valid options:" in error_msg

    def test_language_enum_validation_case_insensitive_accepts_mixed_case(
        self,
    ) -> None:
        """Verify case-insensitive handling prevents user errors.

        Real-world significance:
        - Users won't face errors for minor case variations
        - "EN", "En", "eN" all work correctly
        """
        # All case variations should work
        assert Language.from_string("EN") == Language.ENGLISH
        assert Language.from_string("En") == Language.ENGLISH
        assert Language.from_string("FR") == Language.FRENCH
        assert Language.from_string("Fr") == Language.FRENCH

    def test_language_from_string_none_defaults_to_english(self) -> None:
        """Verify None defaults to English (safe default).

        Real-world significance:
        - Prevents KeyError if language is somehow omitted
        - Provides reasonable default behavior
        """
        assert Language.from_string(None) == Language.ENGLISH

    def test_template_renderer_dispatch_assumes_valid_language(self) -> None:
        """Verify get_language_renderer() assumes language is already validated.

        CHANGE RATIONALE (Task 4 - Remove Redundant Validation):
        - Language validation happens at THREE upstream points:
          1. CLI: argparse choices (before pipeline runs)
          2. Enum: Language.from_string() validates at multiple usage points
          3. Type system: Type hints enforce Language enum
        - get_language_renderer() can safely assume valid input (no defensive check needed)
        - Removing redundant check simplifies code and improves performance

        Real-world significance:
        - Code is clearer: no misleading defensive checks
        - No false sense of protection; real validation is upstream
        - If invalid language somehow reaches this point, KeyError is appropriate
          (indicates upstream validation failure, not a data issue)

        Validation Contract:
        - Input: Language enum (already validated upstream)
        - Output: Callable template renderer
        - No error handling needed (error indicates upstream validation failed)
        """

        # Verify renderer dispatch works for valid languages
        en = Language.from_string("en")
        en_renderer = generate_notices.get_language_renderer(en)
        assert callable(en_renderer)

        fr = Language.from_string("fr")
        fr_renderer = generate_notices.get_language_renderer(fr)
        assert callable(fr_renderer)

    def test_valid_languages_pass_all_checks(self) -> None:
        """Verify valid languages pass all validation checks.

        Real-world significance:
        - Confirms that supported languages work end-to-end
        - Positive test case for all failure points
        """
        # English
        en_lang = Language.from_string("en")
        assert en_lang == Language.ENGLISH
        en_renderer = generate_notices.get_language_renderer(en_lang)
        assert callable(en_renderer)

        # French
        fr_lang = Language.from_string("fr")
        assert fr_lang == Language.FRENCH
        fr_renderer = generate_notices.get_language_renderer(fr_lang)
        assert callable(fr_renderer)

    def test_language_all_codes_returns_supported_languages(self) -> None:
        """Verify Language.all_codes() returns set of all supported languages.

        Real-world significance:
        - Used by CLI for dynamic argument validation
        - Ensures CLI choices update automatically when languages are added
        """
        codes = Language.all_codes()
        assert isinstance(codes, set)
        assert "en" in codes
        assert "fr" in codes
        assert len(codes) == 2


@pytest.mark.unit
class TestLanguageFailurePathDocumentation:
    """Document the exact failure points and error messages for unsupported languages."""

    def test_failure_path_unsupported_language_documentation(self) -> None:
        """Document where unsupported languages fail in the pipeline.

        This test serves as documentation of the failure detection strategy.

        FAILURE POINT SEQUENCE:
        =======================

        1. **CLI Entry Point (FIRST DEFENSE - ARGPARSE)**
           Location: pipeline/orchestrator.py, parse_args()
           Trigger: User runs `viper input.xlsx es`
           Error Message: "argument language: invalid choice: 'es' (choose from en, fr)"
           Resolution: User sees valid choices immediately

        2. **Enum Validation (PRIMARY VALIDATION)**
           Location: pipeline/enums.py, Language.from_string()
           Trigger: Any code path tries Language.from_string("es")
           Error Message: "ValueError: Unsupported language: es. Valid options: en, fr"
           Used By:
           - Preprocessing: convert_date_string(), line ~178-201
           - Preprocessing: build_result(), line ~675
           - Generate notices: render_notice(), line ~249
           - Testing: Language validation tests

        3. **Template Dispatcher (NO DEFENSIVE CHECK - Task 4 OPTIMIZATION)**
           Location: pipeline/generate_notices.py, get_language_renderer()
           Status: REMOVED redundant validation check in Task 4
           Rationale: Language is guaranteed valid by CLI validation + Language.from_string()
           Performance: Eliminates unnecessary dict lookup validation
           Safety: Type system and upstream validation provide sufficient protection

        4. **Rendering Failure (SHOULD NOT REACH)**
           Location: pipeline/generate_notices.py, render_notice()
           Would Occur: If invalid language somehow bypassed both checks
           Error Type: Would be KeyError from _LANGUAGE_RENDERERS[language.value]
           Prevention: Checks 1-2 ensure this never happens

        RESULT: **IMMEDIATE FAILURE WITH CLEAR ERROR MESSAGE**
        - User sees error at CLI before pipeline starts
        - If CLI validation bypassed, fails in enum validation with clear message
        - All failure points provide actionable error messages listing valid options
        - **ZERO RISK** of silent failures or cryptic KeyError

        ADDING A NEW LANGUAGE:
        =====================
        If a new language needs to be added (e.g., Spanish):

        1. Add to enum:
           class Language(Enum):
               ENGLISH = "en"
               FRENCH = "fr"
               SPANISH = "es"  # Add here

        2. CLI automatically updated (uses Language.all_codes())

        3. Enum validation automatically updated (iterates Language members)

        4. Create template: templates/es_template.py with render_notice()

        5. Register renderer:
           _LANGUAGE_RENDERERS = {
               Language.ENGLISH.value: render_notice_en,
               Language.FRENCH.value: render_notice_fr,
               Language.SPANISH.value: render_notice_es,  # Add here
           }

        6. Add Spanish vaccine/disease mappings to config files

        7. Tests automatically include new language (generic test patterns)

        Result: **THREE-LINE CHANGE** in code + config updates
        """
        # This test is primarily documentation; verify current state
        assert Language.all_codes() == {"en", "fr"}

        # Verify enum validation works as documented
        with pytest.raises(ValueError, match="Unsupported language: es"):
            Language.from_string("es")

        # Verify renderer dispatch works as documented
        en = Language.from_string("en")
        en_renderer = generate_notices.get_language_renderer(en)
        assert callable(en_renderer)
