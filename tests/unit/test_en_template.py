"""Unit tests for en_template module - English Typst template generation.

Tests cover:
- Template rendering with client context
- Placeholder substitution (logo, signature, parameters paths)
- Required context key validation
- Error handling for missing context keys
- Template output structure
- Language-specific content (English)

Real-world significance:
- Renders Typst templates for English-language notices
- Part of notice generation pipeline (Step 4)
- Each client gets custom template with QR code, vaccines due, etc.
- Template errors prevent PDF compilation
"""

from __future__ import annotations

import pytest

from templates.en_template import (
    DYNAMIC_BLOCK,
    TEMPLATE_PREFIX,
    render_notice,
)


@pytest.mark.unit
class TestRenderNotice:
    """Unit tests for render_notice function."""

    def test_render_notice_with_valid_context(self) -> None:
        """Verify template renders successfully with all required keys.

        Real-world significance:
        - Template must accept valid context from generate_notices
        - Output should be valid Typst code
        """
        context = {
            "client_row": '("001", "C00001", "John Doe")',
            "client_data": '{name: "John Doe", dob: "2015-03-15"}',
            "vaccines_due_str": '"MMR, DPT"',
            "vaccines_due_array": '("MMR", "DPT")',
            "received": '(("MMR", "2020-05-15"), ("DPT", "2019-03-15"))',
            "num_rows": "2",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        result = render_notice(
            context,
            logo_path="/path/to/logo.png",
            signature_path="/path/to/signature.png",
        )

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain notice and vaccine table sections
        assert "immunization_notice" in result

    def test_render_notice_missing_client_row_raises_error(self) -> None:
        """Verify error when client_row context missing.

        Real-world significance:
        - Missing required field should fail loudly
        - Better than producing invalid Typst
        """
        context = {
            # Missing client_row
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        with pytest.raises(KeyError, match="Missing context keys"):
            render_notice(
                context,
                logo_path="/path/to/logo.png",
                signature_path="/path/to/signature.png",
            )

    def test_render_notice_missing_multiple_keys_raises_error(self) -> None:
        """Verify error lists all missing keys.

        Real-world significance:
        - User can see which fields are missing
        - Helps debug generate_notices step
        """
        context = {
            # Missing multiple required keys
            "client_row": "()",
        }

        with pytest.raises(KeyError, match="Missing context keys"):
            render_notice(
                context,
                logo_path="/path/to/logo.png",
                signature_path="/path/to/signature.png",
            )

    def test_render_notice_substitutes_logo_path(self) -> None:
        """Verify logo path is substituted in template.

        Real-world significance:
        - Logo path must match actual file location
        - Output Typst must reference correct logo path
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        logo_path = "/custom/logo/path.png"
        result = render_notice(
            context,
            logo_path=logo_path,
            signature_path="/sig.png",
        )

        assert logo_path in result

    def test_render_notice_substitutes_signature_path(self) -> None:
        """Verify signature path is substituted in template.

        Real-world significance:
        - Signature path must match actual file location
        - Output Typst must reference correct signature path
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        signature_path = "/custom/signature.png"
        result = render_notice(
            context,
            logo_path="/logo.png",
            signature_path=signature_path,
        )

        assert signature_path in result

    def test_render_notice_includes_template_prefix(self) -> None:
        """Verify output includes template header and imports.

        Real-world significance:
        - Typst setup code must be included
        - Import statement for conf.typ is required
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        result = render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
        )

        # Should include import statement
        assert '#import "/templates/conf.typ"' in result

    def test_render_notice_includes_dynamic_block(self) -> None:
        """Verify output includes dynamic content section.

        Real-world significance:
        - Dynamic block contains client-specific data
        - Must have vaccines_due, vaccines_due_array, etc.
        """
        context = {
            "client_row": '("001", "C00001")',
            "client_data": "{}",
            "vaccines_due_str": '"MMR"',
            "vaccines_due_array": '("MMR")',
            "received": "()",
            "num_rows": "1",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        result = render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
        )

        # Dynamic block placeholders should be substituted
        assert "__CLIENT_ROW__" not in result  # Should be replaced
        assert "__CLIENT_DATA__" not in result  # Should be replaced
        assert '("001", "C00001")' in result  # Actual value should be in output

    def test_render_notice_with_complex_client_data(self) -> None:
        """Verify template handles complex client data structures.

        Real-world significance:
        - Client data might have nested structures
        - Template must accept and preserve complex Typst data structures
        """
        context = {
            "client_row": '("seq_001", "OEN_12345", "Alice Johnson")',
            "client_data": '(name: "Alice Johnson", dob: "2015-03-15", address: "123 Main St")',
            "vaccines_due_str": '"Measles, Mumps, Rubella"',
            "vaccines_due_array": '("Measles", "Mumps", "Rubella")',
            "received": '(("Measles", "2020-05-01"), ("Mumps", "2020-05-01"))',
            "num_rows": "5",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        result = render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
        )

        # Verify complex values are included
        assert "Alice Johnson" in result
        assert "Measles" in result
        assert "Mumps" in result

    def test_render_notice_empty_vaccines_handled(self) -> None:
        """Verify template handles no vaccines due (empty arrays).

        Real-world significance:
        - Child might have all required vaccines
        - Template must handle empty vaccines_due_array
        """
        context = {
            "client_row": "()",
            "client_data": "{}",
            "vaccines_due_str": '""',
            "vaccines_due_array": "()",
            "received": "()",
            "num_rows": "0",
            "chart_diseases_translated": '("Diphtheria", "Tetanus", "Pertussis")',
            "phu_data": {
                "phu_address": "Tunnel Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
                "phu_email": "mainpublichealth#rodenthealth.ca",
                "phu_phone": "555-555-5555 ext. 1234",
                "phu_website": "https://www.test-immunization.ca",
            },
        }

        result = render_notice(
            context,
            logo_path="/logo.png",
            signature_path="/sig.png",
        )

        # Should still render successfully
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.unit
class TestTemplateConstants:
    """Unit tests for template constant definitions."""

    def test_template_prefix_contains_imports(self) -> None:
        """Verify TEMPLATE_PREFIX includes required imports.

        Real-world significance:
        - Typst must import conf.typ helpers
        - Setup code must be present
        """
        assert '#import "/templates/conf.typ"' in TEMPLATE_PREFIX

    def test_template_prefix_contains_function_definitions(self) -> None:
        """Verify TEMPLATE_PREFIX defines helper functions.

        Real-world significance:
        - immunization_notice() function must be defined
        - Functions used in dynamic block must exist
        """
        assert "immunization_notice" in TEMPLATE_PREFIX

    def test_dynamic_block_contains_placeholders(self) -> None:
        """Verify DYNAMIC_BLOCK has all substitution placeholders.

        Real-world significance:
        - Each placeholder corresponds to a context key
        - Missing placeholder = lost data in output
        """
        assert "__CLIENT_ROW__" in DYNAMIC_BLOCK
        assert "__CLIENT_DATA__" in DYNAMIC_BLOCK
        assert "__VACCINES_DUE_STR__" in DYNAMIC_BLOCK
        assert "__VACCINES_DUE_ARRAY__" in DYNAMIC_BLOCK
        assert "__RECEIVED__" in DYNAMIC_BLOCK
        assert "__NUM_ROWS__" in DYNAMIC_BLOCK

    def test_template_prefix_contains_placeholder_markers(self) -> None:
        """Verify TEMPLATE_PREFIX has path placeholders to substitute.

        Real-world significance:
        - Logo and signature paths must be replaceable
        - Parameters path no longer used (date pre-formatted in Python)
        """
        assert "__LOGO_PATH__" in TEMPLATE_PREFIX
        assert "__SIGNATURE_PATH__" in TEMPLATE_PREFIX
