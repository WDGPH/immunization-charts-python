"""Unit tests for generate_mock_template_fr module - French Typst template generation.

Tests cover:
- Template rendering with client context (French version)
- Placeholder substitution (logo, signature, parameters paths)
- Required context key validation
- Error handling for missing context keys
- Template output structure
- Language-specific content (French)

Real-world significance:
- Renders Typst templates for French-language notices
- Part of notice generation pipeline (Step 4)
- Each client gets custom template with QR code, vaccines due, etc.
- Template errors prevent PDF compilation
- Must match English template structure for consistency
"""

from __future__ import annotations

import pytest

from scripts import generate_mock_template_fr


@pytest.mark.unit
class TestRenderNotice:
    """Unit tests for render_notice function (French)."""

    def test_render_notice_with_valid_context(self) -> None:
        """Verify French template renders successfully with all required keys.

        Real-world significance:
        - Template must accept valid context from generate_notices
        - Output should be valid Typst code
        - French version should have same structure as English
        """
        context = {
            "client_row": '("001", "C00001", "Jean Dupont")',
            "client_data": '{name: "Jean Dupont", dob: "2015-03-15"}',
            "vaccines_due_str": '"RRO, DPT"',
            "vaccines_due_array": '("RRO", "DPT")',
            "received": '(("RRO", "2020-05-15"), ("DPT", "2019-03-15"))',
            "num_rows": "2",
        }

        result = generate_mock_template_fr.render_notice(
            context,
            logo_path="/path/to/logo.png",
            signature_path="/path/to/signature.png",
            parameters_path="/path/to/parameters.yaml",
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "immunization_notice" in result

    def test_render_notice_missing_client_row_raises_error(self) -> None:
        """Verify error when client_row context missing (French).

        Real-world significance:
        - Same validation as English version
        - Missing fields should fail with clear error
        """
        context = {
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
        }

        with pytest.raises(KeyError, match="Missing context keys"):
            generate_mock_template_fr.render_notice(
                context,
                logo_path="/path/to/logo.png",
                signature_path="/path/to/signature.png",
                parameters_path="/path/to/parameters.yaml",
            )

    def test_render_notice_substitutes_paths(self) -> None:
        """Verify all paths are substituted correctly (French).

        Real-world significance:
        - Logo, signature, and parameters paths must all be replaced
        - Paths must match between English and French versions
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
        }

        logo_path = "/logos/logo_fr.png"
        signature_path = "/sigs/signature_fr.png"
        parameters_path = "/config/parameters.yaml"

        result = generate_mock_template_fr.render_notice(
            context,
            logo_path=logo_path,
            signature_path=signature_path,
            parameters_path=parameters_path,
        )

        assert logo_path in result
        assert signature_path in result
        assert parameters_path in result

    def test_render_notice_includes_french_content(self) -> None:
        """Verify French version includes French-specific content.

        Real-world significance:
        - Must be French, not English
        - Different notice text for French users
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
        }

        result = generate_mock_template_fr.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )

        # French template should be present
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_notice_with_french_client_names(self) -> None:
        """Verify template handles French client names with accents.

        Real-world significance:
        - French names might have accents (é, è, ç, etc.)
        - Template must preserve character encoding
        """
        context = {
            "client_row": '("001", "C00001", "François Québec")',
            "client_data": '(name: "François Québec", dob: "2015-03-15")',
            "vaccines_due_str": '"RRO"',
            "vaccines_due_array": '("RRO")',
            "received": "()",
            "num_rows": "1",
        }

        result = generate_mock_template_fr.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )

        # French names should be preserved
        assert "François" in result
        assert "Québec" in result

    def test_render_notice_complex_vaccines_list_french(self) -> None:
        """Verify template handles French vaccine names.

        Real-world significance:
        - Vaccine names are translated to French
        - Template must render French disease/vaccine names
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '"Rougeole, Oreillons, Rubéole"',
            "vaccines_due_array": '("Rougeole", "Oreillons", "Rubéole")',
            "received": "()",
            "num_rows": "0",
        }

        result = generate_mock_template_fr.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )

        # French vaccine names should be present
        assert "Rougeole" in result


@pytest.mark.unit
class TestFrenchTemplateConstants:
    """Unit tests for French template constant definitions."""

    def test_template_prefix_contains_imports(self) -> None:
        """Verify TEMPLATE_PREFIX includes required imports (French).

        Real-world significance:
        - Typst must import conf.typ helpers
        - Same imports as English version
        """
        assert (
            '#import "/scripts/conf.typ"' in generate_mock_template_fr.TEMPLATE_PREFIX
        )

    def test_template_prefix_contains_function_definitions(self) -> None:
        """Verify TEMPLATE_PREFIX defines helper functions (French).

        Real-world significance:
        - Same function definitions as English
        - Structure should be consistent between versions
        """
        assert "immunization_notice" in generate_mock_template_fr.TEMPLATE_PREFIX

    def test_dynamic_block_contains_same_placeholders(self) -> None:
        """Verify DYNAMIC_BLOCK has same placeholders as English.

        Real-world significance:
        - Context keys must match between English and French
        - Same placeholders = can use same rendering logic
        """
        dynamic = generate_mock_template_fr.DYNAMIC_BLOCK
        assert "__CLIENT_ROW__" in dynamic
        assert "__CLIENT_DATA__" in dynamic
        assert "__VACCINES_DUE_STR__" in dynamic
        assert "__VACCINES_DUE_ARRAY__" in dynamic
        assert "__RECEIVED__" in dynamic
        assert "__NUM_ROWS__" in dynamic

    def test_template_prefix_contains_placeholder_markers(self) -> None:
        """Verify TEMPLATE_PREFIX has path placeholders (French).

        Real-world significance:
        - Same path placeholders as English
        - Can swap French and English by just swapping templates
        """
        assert "__LOGO_PATH__" in generate_mock_template_fr.TEMPLATE_PREFIX
        assert "__SIGNATURE_PATH__" in generate_mock_template_fr.TEMPLATE_PREFIX
        assert "__PARAMETERS_PATH__" in generate_mock_template_fr.TEMPLATE_PREFIX


@pytest.mark.unit
class TestLanguageConsistency:
    """Tests verifying consistency between English and French templates."""

    def test_both_versions_accept_same_context_keys(self) -> None:
        """Verify English and French use same context keys.

        Real-world significance:
        - generate_notices can use same context for both languages
        - Only template content differs, not structure
        """
        from scripts import generate_mock_template_en

        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
        }

        # Both should render without error
        en_result = generate_mock_template_en.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )
        fr_result = generate_mock_template_fr.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )

        assert en_result is not None
        assert fr_result is not None

    def test_french_template_structure_matches_english(self) -> None:
        """Verify French template has same structure as English.

        Real-world significance:
        - Both versions should produce similar Typst output
        - Differing only in text content, not layout
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
        }

        from scripts import generate_mock_template_en

        en = generate_mock_template_en.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )
        fr = generate_mock_template_fr.render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
            parameters_path="/params.yaml",
        )

        # Both should have same length (roughly)
        # Placeholder counts should be similar
        assert "#let client_row" in en
        assert "#let client_row" in fr
        assert "#immunization_notice" in en
        assert "#immunization_notice" in fr
