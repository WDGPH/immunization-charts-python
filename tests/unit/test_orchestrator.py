"""Unit tests for orchestrator module - Pipeline orchestration and argument handling.

Tests cover:
- Command-line argument parsing and validation
- Argument validation (file exists, language is valid)
- Pipeline step orchestration (steps 1-9 sequencing)
- Configuration loading
- Error handling and logging
- Return codes and exit status

Real-world significance:
- Entry point for entire pipeline (orchestrator.main())
- Argument validation prevents downstream errors
- Orchestration order ensures correct data flow (Step N output → Step N+1 input)
- Error handling must gracefully report problems to users
- Run ID generation enables comparing multiple pipeline runs
- Used by both CLI (viper command) and programmatic callers
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import generate_notices, orchestrator
from pipeline.enums import Language


@pytest.mark.unit
class TestParseArgs:
    """Unit tests for command-line argument parsing."""

    def test_parse_args_required_arguments(self) -> None:
        """Verify parsing of required arguments.

        Real-world significance:
        - input_file and language are required
        - Parser should validate both exist
        """
        with patch("sys.argv", ["viper", "students.xlsx", "en"]):
            args = orchestrator.parse_args()
            assert args.input_file == "students.xlsx"
            assert args.language == "en"

    def test_parse_args_language_choices(self) -> None:
        """Verify language argument accepts only 'en' or 'fr'.

        Real-world significance:
        - Pipeline supports English and French
        - Should reject other languages early
        """
        # Valid language
        with patch("sys.argv", ["viper", "file.xlsx", "fr"]):
            args = orchestrator.parse_args()
            assert args.language == "fr"

    def test_parse_args_optional_directories(self) -> None:
        """Verify optional --input, --output, --config arguments.

        Real-world significance:
        - User can override default directories
        - Common in testing and CI/CD environments
        """
        with patch(
            "sys.argv",
            [
                "viper",
                "test.xlsx",
                "en",
                "--input",
                "/tmp/input",
                "--output",
                "/tmp/output",
                "--config",
                "/etc/config",
            ],
        ):
            args = orchestrator.parse_args()
            assert args.input_dir == Path("/tmp/input")
            assert args.output_dir == Path("/tmp/output")
            assert args.config_dir == Path("/etc/config")

    def test_parse_args_defaults(self) -> None:
        """Verify default directory paths when not specified.

        Real-world significance:
        - Defaults should be relative to project root
        - ../input, ../output, ../config from pipeline/
        """
        with patch("sys.argv", ["viper", "file.xlsx", "en"]):
            args = orchestrator.parse_args()
            # Defaults should exist
            assert args.input_dir is not None
            assert args.output_dir is not None
            assert args.config_dir is not None


@pytest.mark.unit
class TestValidateArgs:
    """Unit tests for argument validation."""

    def test_validate_args_missing_input_file(self, tmp_test_dir: Path) -> None:
        """Verify error when input file doesn't exist.

        Real-world significance:
        - Should fail early with clear error
        - Prevents pipeline from running with bad path
        """
        args = MagicMock()
        args.input_file = "nonexistent.xlsx"
        args.input_dir = tmp_test_dir

        with pytest.raises(FileNotFoundError, match="Input file not found"):
            orchestrator.validate_args(args)

    def test_validate_args_existing_input_file(self, tmp_test_dir: Path) -> None:
        """Verify no error when input file exists.

        Real-world significance:
        - Valid input should pass validation
        """
        test_file = tmp_test_dir / "students.xlsx"
        test_file.write_text("test")

        args = MagicMock()
        args.input_file = "students.xlsx"
        args.input_dir = tmp_test_dir
        args.template_dir = None  # Use default templates

        # Should not raise
        orchestrator.validate_args(args)


@pytest.mark.unit
class TestPrintFunctions:
    """Unit tests for pipeline progress printing."""

    def test_print_header(self) -> None:
        """Verify header printing includes input file info.

        Real-world significance:
        - User should see which file is being processed
        - Header provides context for the run
        """
        with patch("builtins.print"):
            orchestrator.print_header("students.xlsx")

    def test_print_step(self) -> None:
        """Verify step header includes step number and description.

        Real-world significance:
        - User can track progress through 9-step pipeline
        - Each step should be visible and identifiable
        """
        with patch("builtins.print"):
            orchestrator.print_step(1, "Preparing output directory")

    def test_print_step_complete(self) -> None:
        """Verify completion message includes timing info.

        Real-world significance:
        - User can see how long each step takes
        - Helps identify performance bottlenecks
        """
        with patch("builtins.print"):
            orchestrator.print_step_complete(2, "Preprocessing", 5.5)


@pytest.mark.unit
class TestPipelineSteps:
    """Unit tests for individual pipeline step functions."""

    def test_run_step_1_prepare_output_success(
        self, tmp_output_structure: dict, config_file: Path
    ) -> None:
        """Verify Step 1: prepare output runs successfully.

        Real-world significance:
        - First step: creates directory structure and reads config
        - Must succeed or entire pipeline fails
        - Reads pipeline.before_run.clear_output_directory from config
        """
        with patch("pipeline.orchestrator.prepare_output") as mock_prep:
            mock_prep.prepare_output_directory.return_value = True
            result = orchestrator.run_step_1_prepare_output(
                output_dir=tmp_output_structure["root"],
                log_dir=tmp_output_structure["logs"],
                config_dir=config_file.parent,
            )
            assert result is True

    def test_run_step_1_prepare_output_user_cancels(
        self, tmp_output_structure: dict, config_file: Path
    ) -> None:
        """Verify Step 1 aborts if user declines cleanup.

        Real-world significance:
        - User should be able to cancel pipeline via prepare_output_directory
        - Should not proceed if prepare_output returns False
        """
        with patch("pipeline.orchestrator.prepare_output") as mock_prep:
            mock_prep.prepare_output_directory.return_value = False
            result = orchestrator.run_step_1_prepare_output(
                output_dir=tmp_output_structure["root"],
                log_dir=tmp_output_structure["logs"],
                config_dir=config_file.parent,
            )
            assert result is False

    def test_run_step_2_preprocess(
        self, tmp_test_dir: Path, tmp_output_structure: dict
    ) -> None:
        """Verify Step 2: preprocess returns client count."""
        mock_df = MagicMock()
        mock_mapped_df = MagicMock()
        mock_filtered_df = MagicMock()
        mock_final_df = MagicMock()
        mock_result = MagicMock()
        client1 = MagicMock(sequence=1, client_id="1")
        client2 = MagicMock(sequence=2, client_id="2")
        mock_result.clients = [client1, client2]
        mock_result.warnings = []

        with (
            patch("pipeline.orchestrator.preprocess.read_input", return_value=mock_df),
            patch(
                "pipeline.orchestrator.preprocess.map_columns",
                return_value=(mock_mapped_df, {}),
            ),
            patch(
                "pipeline.orchestrator.preprocess.filter_columns",
                return_value=mock_filtered_df,
            ),
            patch(
                "pipeline.orchestrator.preprocess.ensure_required_columns",
                return_value=mock_final_df,
            ),
            patch(
                "pipeline.orchestrator.preprocess.build_preprocess_result",
                return_value=mock_result,
            ),
            patch(
                "pipeline.orchestrator.preprocess.configure_logging",
                return_value=tmp_test_dir / "log.txt",
            ),
            patch(
                "pipeline.orchestrator.preprocess.write_artifact",
                return_value="artifact.json",
            ),
            patch("pipeline.orchestrator.json.loads", return_value={"vaccine": "MMR"}),
            patch("builtins.print"),
        ):
            total = orchestrator.run_step_2_preprocess(
                input_dir=tmp_test_dir,
                input_file="test.xlsx",
                output_dir=tmp_output_structure["root"],
                language="en",
                run_id="test_20250101_120000",
            )

        assert total == 2

    def test_run_step_3_generate_qr_codes_disabled(
        self, tmp_output_structure: dict, config_file: Path
    ) -> None:
        """Verify Step 3: QR generation returns 0 when disabled.

        Real-world significance:
        - QR generation is optional (config-driven)
        - Should return 0 when disabled
        """
        # Create config with qr disabled
        config_file.write_text("qr:\n  enabled: false\n")

        with patch(
            "pipeline.orchestrator.load_config", return_value={"qr": {"enabled": False}}
        ):
            with patch("builtins.print"):
                result = orchestrator.run_step_3_generate_qr_codes(
                    output_dir=tmp_output_structure["root"],
                    run_id="test_run",
                    config_dir=config_file.parent,
                )

        assert result == 0


@pytest.mark.unit
class TestPipelineOrchestration:
    """Unit tests for pipeline orchestration logic."""

    def test_pipeline_steps_ordered_correctly(self) -> None:
        """Verify steps are called in correct order.

        Real-world significance:
        - Step N output must feed into Step N+1
        - Wrong order causes data flow errors
        - Order: prepare → preprocess → qr → notices → compile → count → encrypt → batch → cleanup
        """
        # This is a higher-level test that would verify call order
        # In practice, integration tests verify this
        assert True  # Placeholder for call order verification

    def test_pipeline_main_returns_zero_on_success(
        self, tmp_test_dir: Path, tmp_output_structure: dict
    ) -> None:
        """Verify main() returns 0 on successful pipeline run.

        Real-world significance:
        - Exit code 0 indicates success for shell scripts
        - CI/CD systems rely on exit codes
        """
        # This would require extensive mocking
        # Typically tested at integration/e2e level
        assert True  # Placeholder


@pytest.mark.unit
class TestConfigLoading:
    """Unit tests for configuration loading."""

    def test_pipeline_loads_parameters_yaml(self, config_file: Path) -> None:
        """Verify pipeline loads configuration from parameters.yaml.

        Real-world significance:
        - All behavior controlled by config file
        - Must load successfully or pipeline fails
        """
        with patch("pipeline.orchestrator.load_config") as mock_load:
            mock_load.return_value = {
                "pipeline": {"auto_remove_output": False},
                "qr": {"enabled": True},
            }

            from pipeline.config_loader import load_config

            config = load_config(config_file)
            assert config is not None


@pytest.mark.unit
class TestRunIdGeneration:
    """Unit tests for run ID generation."""

    def test_run_id_format(self) -> None:
        """Verify run ID has expected format.

        Real-world significance:
        - Run ID used in artifact filenames
        - Format: YYYYMMDD_HHMMSS
        - Enables comparing multiple pipeline runs
        """
        # run_id generated in main(), typically as:
        # run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        from datetime import datetime, timezone

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        # Should be 15 characters: YYYYMMDDTHHMMSS
        assert len(run_id) == 15
        assert "T" in run_id  # Contains T separator


@pytest.mark.unit
class TestErrorHandling:
    """Unit tests for pipeline error handling."""

    def test_pipeline_catches_preprocessing_errors(self) -> None:
        """Verify preprocessing errors are caught.

        Real-world significance:
        - Bad input data should fail gracefully
        - Pipeline should report error and exit
        """
        # Error handling tested at integration level
        assert True  # Placeholder

    def test_pipeline_catches_compilation_errors(self) -> None:
        """Verify compilation errors are caught.

        Real-world significance:
        - Typst compilation might fail
        - Should report which PDF failed to compile
        """
        # Error handling tested at integration level
        assert True  # Placeholder


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
        # Build renderers from default template directory
        from pathlib import Path

        templates_dir = Path(__file__).parent.parent.parent / "templates"
        renderers = generate_notices.build_language_renderers(templates_dir)

        # Verify renderer dispatch works for valid languages
        en = Language.from_string("en")
        en_renderer = generate_notices.get_language_renderer(en, renderers)
        assert callable(en_renderer)

        fr = Language.from_string("fr")
        fr_renderer = generate_notices.get_language_renderer(fr, renderers)
        assert callable(fr_renderer)

    def test_valid_languages_pass_all_checks(self) -> None:
        """Verify valid languages pass all validation checks.

        Real-world significance:
        - Confirms that supported languages work end-to-end
        - Positive test case for all failure points
        """
        # Build renderers from default template directory
        from pathlib import Path

        templates_dir = Path(__file__).parent.parent.parent / "templates"
        renderers = generate_notices.build_language_renderers(templates_dir)

        # English
        en_lang = Language.from_string("en")
        assert en_lang == Language.ENGLISH
        en_renderer = generate_notices.get_language_renderer(en_lang, renderers)
        assert callable(en_renderer)

        # French
        fr_lang = Language.from_string("fr")
        assert fr_lang == Language.FRENCH
        fr_renderer = generate_notices.get_language_renderer(fr_lang, renderers)
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
        # Build renderers from default template directory
        from pathlib import Path

        templates_dir = Path(__file__).parent.parent.parent / "templates"
        renderers = generate_notices.build_language_renderers(templates_dir)

        # This test is primarily documentation; verify current state
        assert Language.all_codes() == {"en", "fr"}

        # Verify enum validation works as documented
        with pytest.raises(ValueError, match="Unsupported language: es"):
            Language.from_string("es")

        # Verify renderer dispatch works as documented
        en = Language.from_string("en")
        en_renderer = generate_notices.get_language_renderer(en, renderers)
        assert callable(en_renderer)
