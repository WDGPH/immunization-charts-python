"""Unit tests for dynamic template loading functions.

Tests cover:
- load_template_module() function
- build_language_renderers() function
- Error handling for missing templates
- Error handling for invalid modules

Real-world significance:
- Dynamic loading enables custom template directories
- Error messages must be clear and actionable
- Validation must catch configuration errors early
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import generate_notices


@pytest.mark.unit
class TestLoadTemplateModule:
    """Unit tests for load_template_module function."""

    @pytest.fixture
    def templates_dir(self) -> Path:
        """Provide path to default templates directory."""
        return Path(__file__).parent.parent.parent / "templates"

    @pytest.fixture
    def custom_templates_dir(self) -> Path:
        """Provide path to custom templates directory."""
        return Path(__file__).parent.parent / "fixtures" / "custom_templates"

    def test_load_template_module_success_en_from_default(
        self, templates_dir: Path
    ) -> None:
        """Verify English template module loads from default templates.

        Real-world significance:
        - Dynamic loading must work for standard templates
        - Module must have render_notice function
        """
        module = generate_notices.load_template_module(templates_dir, "en")

        assert hasattr(module, "render_notice")
        assert callable(module.render_notice)

    def test_load_template_module_success_fr_from_default(
        self, templates_dir: Path
    ) -> None:
        """Verify French template module loads from default templates."""
        module = generate_notices.load_template_module(templates_dir, "fr")

        assert hasattr(module, "render_notice")
        assert callable(module.render_notice)

    def test_load_template_module_success_from_custom(
        self, custom_templates_dir: Path
    ) -> None:
        """Verify template module loads from custom directory.

        Real-world significance:
        - Custom templates must be loadable dynamically
        - Enables PHU-specific template customization
        """
        if not custom_templates_dir.exists():
            pytest.skip("Custom templates directory not set up")

        module = generate_notices.load_template_module(custom_templates_dir, "en")

        assert hasattr(module, "render_notice")
        assert callable(module.render_notice)

    def test_load_template_module_missing_file(self, tmp_path: Path) -> None:
        """Verify error raised when template file doesn't exist.

        Real-world significance:
        - User provides wrong template directory
        - Should fail with clear error message
        """
        with pytest.raises(FileNotFoundError, match="Template module not found"):
            generate_notices.load_template_module(tmp_path, "en")

    def test_load_template_module_missing_file_error_mentions_path(
        self, tmp_path: Path
    ) -> None:
        """Verify error message includes expected path.

        Real-world significance:
        - User can see exactly what path was searched
        - Helps troubleshoot configuration issues
        """
        with pytest.raises(FileNotFoundError) as exc_info:
            generate_notices.load_template_module(tmp_path, "en")

        error_msg = str(exc_info.value)
        assert "en_template.py" in error_msg
        assert str(tmp_path) in error_msg

    def test_load_template_module_missing_render_notice(self, tmp_path: Path) -> None:
        """Verify error raised when module lacks render_notice().

        Real-world significance:
        - Template file exists but is invalid
        - Should fail with clear message about missing function
        """
        # Create invalid template file
        invalid_template = tmp_path / "en_template.py"
        invalid_template.write_text("# Empty template\n", encoding="utf-8")

        with pytest.raises(AttributeError, match="must define render_notice"):
            generate_notices.load_template_module(tmp_path, "en")

    def test_load_template_module_missing_render_notice_mentions_file(
        self, tmp_path: Path
    ) -> None:
        """Verify error message mentions template file path.

        Real-world significance:
        - User knows which file has the problem
        - Can look at file to see what's wrong
        """
        invalid_template = tmp_path / "en_template.py"
        invalid_template.write_text("# Empty template\n", encoding="utf-8")

        with pytest.raises(AttributeError) as exc_info:
            generate_notices.load_template_module(tmp_path, "en")

        error_msg = str(exc_info.value)
        assert str(invalid_template) in error_msg

    def test_load_template_module_syntax_error_in_template(self, tmp_path: Path) -> None:
        """Verify error when template has syntax errors.

        Real-world significance:
        - Catches Python errors in template modules
        - Fail-fast prevents confusing later errors
        """
        invalid_template = tmp_path / "en_template.py"
        invalid_template.write_text("this is not valid python }{", encoding="utf-8")

        with pytest.raises(Exception):  # SyntaxError or similar
            generate_notices.load_template_module(tmp_path, "en")


@pytest.mark.unit
class TestBuildLanguageRenderers:
    """Unit tests for build_language_renderers function."""

    @pytest.fixture
    def templates_dir(self) -> Path:
        """Provide path to default templates directory."""
        return Path(__file__).parent.parent.parent / "templates"

    @pytest.fixture
    def custom_templates_dir(self) -> Path:
        """Provide path to custom templates directory."""
        return Path(__file__).parent.parent / "fixtures" / "custom_templates"

    def test_build_language_renderers_success_from_default(
        self, templates_dir: Path
    ) -> None:
        """Verify all language renderers built from default templates.

        Real-world significance:
        - Must load all configured languages
        - Renderer dict used throughout notice generation
        """
        renderers = generate_notices.build_language_renderers(templates_dir)

        # Should have renderer for each language
        assert "en" in renderers
        assert "fr" in renderers
        assert callable(renderers["en"])
        assert callable(renderers["fr"])

    def test_build_language_renderers_success_from_custom(
        self, custom_templates_dir: Path
    ) -> None:
        """Verify all language renderers built from custom templates."""
        if not custom_templates_dir.exists():
            pytest.skip("Custom templates directory not set up")

        renderers = generate_notices.build_language_renderers(custom_templates_dir)

        assert "en" in renderers
        assert "fr" in renderers
        assert callable(renderers["en"])
        assert callable(renderers["fr"])

    def test_build_language_renderers_missing_language(self, tmp_path: Path) -> None:
        """Verify error when template missing for a language.

        Real-world significance:
        - Template directory incomplete
        - Should fail immediately before processing clients
        """
        # Create only English template
        en_template = tmp_path / "en_template.py"
        en_template.write_text(
            "def render_notice(context, *, logo_path, signature_path): return ''",
            encoding="utf-8",
        )

        # Should fail when trying to load French
        with pytest.raises(FileNotFoundError, match="fr_template.py"):
            generate_notices.build_language_renderers(tmp_path)

    def test_build_language_renderers_returns_dict_with_correct_types(
        self, templates_dir: Path
    ) -> None:
        """Verify return type is dict with callable values.

        Real-world significance:
        - Type checking catches misconfigurations
        - Callables can be used as template renderers
        """
        renderers = generate_notices.build_language_renderers(templates_dir)

        assert isinstance(renderers, dict)
        for lang_code, renderer in renderers.items():
            assert isinstance(lang_code, str)
            assert callable(renderer)

    def test_build_language_renderers_multiple_calls_independent(
        self, templates_dir: Path
    ) -> None:
        """Verify multiple calls create independent renderer instances.

        Real-world significance:
        - Pipeline can create renderers multiple times
        - Each call loads modules fresh (separate instances)
        """
        renderers1 = generate_notices.build_language_renderers(templates_dir)
        renderers2 = generate_notices.build_language_renderers(templates_dir)

        # Different dicts (not same object)
        assert renderers1 is not renderers2

        # Different function objects (fresh module loads each time)
        # This is expected with dynamic loading - each call creates new module instances
        assert renderers1["en"] is not renderers2["en"]
        assert renderers1["fr"] is not renderers2["fr"]

        # But they should behave the same way (callable with same signature)
        assert callable(renderers1["en"])
        assert callable(renderers2["en"])
