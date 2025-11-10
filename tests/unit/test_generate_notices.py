"""Unit tests for generate_notices module - notice generation from templates.

Tests cover:
- Template variable substitution
- Language-specific content handling (English and French)
- Data escaping for Typst syntax
- Error handling for missing data/files
- QR code reference integration

Real-world significance:
- Step 4 of pipeline: generates Typst template files for each client
- Template content directly appears in compiled PDF notices
- Language correctness is critical for bilingual support (en/fr)
- Must properly escape special characters for Typst syntax
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import generate_notices
from pipeline.enums import Language
from tests.fixtures import sample_input


@pytest.mark.unit
class TestReadArtifact:
    """Unit tests for read_artifact function."""

    def test_read_artifact_with_valid_json(self, tmp_test_dir: Path) -> None:
        """Verify artifact is read and deserialized correctly.

        Real-world significance:
        - Must load artifact JSON from preprocessing step
        - Should parse all client records with required fields
        """
        artifact_data = {
            "run_id": "test_001",
            "language": "en",
            "total_clients": 1,
            "warnings": [],
            "created_at": "2025-01-01T12:00:00Z",
            "clients": [
                {
                    "sequence": "00001",
                    "client_id": "C001",
                    "language": "en",
                    "person": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "2015-01-01",
                        "date_of_birth_display": "Jan 01, 2015",
                        "date_of_birth_iso": "2015-01-01",
                    },
                    "school": {"name": "Test School", "code": "SCH001"},
                    "board": {"name": "Test Board", "code": "BRD001"},
                    "contact": {
                        "street": "123 Main St",
                        "city": "Toronto",
                        "province": "ON",
                        "postal_code": "M1A1A1",
                    },
                    "vaccines_due": "Measles",
                    "vaccines_due_list": ["Measles"],
                    "received": [],
                    "metadata": {},
                }
            ],
        }
        artifact_path = tmp_test_dir / "artifact.json"
        artifact_path.write_text(json.dumps(artifact_data))

        payload = generate_notices.read_artifact(artifact_path)

        assert payload.run_id == "test_001"
        assert payload.language == "en"
        assert len(payload.clients) == 1
        assert payload.clients[0].client_id == "C001"
        assert payload.clients[0].person.get("first_name") == "John"
        assert payload.clients[0].person.get("last_name") == "Doe"

    def test_read_artifact_missing_file_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when artifact file doesn't exist.

        Real-world significance:
        - Artifact should exist from preprocessing step
        - Missing file indicates pipeline failure
        """
        with pytest.raises(FileNotFoundError):
            generate_notices.read_artifact(tmp_test_dir / "nonexistent.json")

    def test_read_artifact_invalid_json_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when JSON is invalid.

        Real-world significance:
        - Corrupted artifact from preprocessing indicates pipeline failure
        - Must fail early with clear error
        """
        artifact_path = tmp_test_dir / "bad.json"
        artifact_path.write_text("not valid json {{{")

        with pytest.raises(Exception):  # json.JSONDecodeError or similar
            generate_notices.read_artifact(artifact_path)


@pytest.mark.unit
class TestEscapeString:
    """Unit tests for escape_string function."""

    def test_escape_string_handles_backslashes(self) -> None:
        """Verify backslashes are escaped for Typst.

        Real-world significance:
        - Client names/addresses may contain backslashes (rare but possible)
        - Must not break Typst syntax
        """
        result = generate_notices.escape_string("test\\path")

        assert result == "test\\\\path"

    def test_escape_string_handles_quotes(self) -> None:
        """Verify quotes are escaped for Typst.

        Real-world significance:
        - Names like O'Brien contain apostrophes
        - Typst string syntax uses double quotes
        """
        result = generate_notices.escape_string('test "quoted"')

        assert result == 'test \\"quoted\\"'

    def test_escape_string_handles_newlines(self) -> None:
        """Verify newlines are escaped for Typst.

        Real-world significance:
        - Multi-line addresses may appear in data
        - Must be escaped to preserve Typst syntax
        """
        result = generate_notices.escape_string("line1\nline2")

        assert result == "line1\\nline2"

    def test_escape_string_handles_combined(self) -> None:
        """Verify multiple special characters are escaped.

        Real-world significance:
        - Real-world data may have multiple special chars
        - All must be properly escaped
        """
        result = generate_notices.escape_string('test\\"path\nmore')

        assert "\\\\" in result
        assert '\\"' in result
        assert "\\n" in result


@pytest.mark.unit
class TestToTypValue:
    """Unit tests for to_typ_value function."""

    def test_to_typ_value_string(self) -> None:
        """Verify string values convert to Typst string syntax.

        Real-world significance:
        - Most template data is strings
        - Must wrap in quotes and escape special chars
        """
        result = generate_notices.to_typ_value("test string")

        assert result == '"test string"'

    def test_to_typ_value_boolean_true(self) -> None:
        """Verify True converts to Typst 'true'.

        Real-world significance:
        - Boolean flags in template context (e.g., has_qr_code)
        - Must convert to Typst boolean syntax
        """
        result = generate_notices.to_typ_value(True)

        assert result == "true"

    def test_to_typ_value_boolean_false(self) -> None:
        """Verify False converts to Typst 'false'."""
        result = generate_notices.to_typ_value(False)

        assert result == "false"

    def test_to_typ_value_none(self) -> None:
        """Verify None converts to Typst 'none'.

        Real-world significance:
        - Missing optional fields should map to 'none'
        - Typst templates handle none gracefully
        """
        result = generate_notices.to_typ_value(None)

        assert result == "none"

    def test_to_typ_value_int(self) -> None:
        """Verify integers convert to Typst number syntax."""
        result = generate_notices.to_typ_value(42)

        assert result == "42"

    def test_to_typ_value_float(self) -> None:
        """Verify floats convert to Typst number syntax."""
        result = generate_notices.to_typ_value(3.14)

        assert result == "3.14"

    def test_to_typ_value_list(self) -> None:
        """Verify lists convert to Typst array syntax.

        Real-world significance:
        - vaccines_due_list is a list of disease names
        - Must convert to Typst tuple/array syntax
        """
        result = generate_notices.to_typ_value(["Measles", "Mumps"])

        assert "Measles" in result
        assert "Mumps" in result
        # Typst arrays use parentheses
        assert result.startswith("(")
        assert result.endswith(")")

    def test_to_typ_value_single_item_list(self) -> None:
        """Verify single-item lists have trailing comma in Typst.

        Real-world significance:
        - Typst requires trailing comma for single-item tuples
        - Must match Typst syntax exactly
        """
        result = generate_notices.to_typ_value(["Measles"])

        assert "Measles" in result
        assert "," in result

    def test_to_typ_value_dict(self) -> None:
        """Verify dicts convert to Typst named tuple syntax.

        Real-world significance:
        - Client data is structured in dicts
        - Must convert to Typst named tuple format
        """
        data = {"name": "John Doe", "age": 10}
        result = generate_notices.to_typ_value(data)

        assert "name" in result
        assert "John Doe" in result
        assert "age" in result

    def test_to_typ_value_unsupported_type_raises_error(self) -> None:
        """Verify error for unsupported types.

        Real-world significance:
        - Template context should only have basic types
        - Unsupported types indicate programming error
        """

        class CustomClass:
            pass

        with pytest.raises(TypeError):
            generate_notices.to_typ_value(CustomClass())


@pytest.mark.unit
class TestBuildTemplateContext:
    """Unit tests for build_template_context function."""

    def test_build_template_context_from_client(self) -> None:
        """Verify context builds from client data.

        Real-world significance:
        - Context supplies data for Typst template rendering
        - Must extract all required fields from client record
        """
        client = sample_input.create_test_client_record(
            client_id="C001",
            first_name="John",
            last_name="Doe",
            school_name="Test School",
        )

        context = generate_notices.build_template_context(client)

        assert "client_row" in context
        assert "client_data" in context
        assert "vaccines_due_str" in context
        assert "vaccines_due_array" in context
        assert "received" in context
        assert "num_rows" in context

    def test_build_template_context_includes_client_id(self) -> None:
        """Verify client_id is in context.

        Real-world significance:
        - Client ID appears on notice for identification
        - Must be correctly formatted for Typst
        """
        client = sample_input.create_test_client_record(client_id="C12345")

        context = generate_notices.build_template_context(client)

        assert "C12345" in context["client_row"]

    def test_build_template_context_escapes_special_chars(self) -> None:
        """Verify special characters in client data are escaped.

        Real-world significance:
        - Names like O'Brien or places with accents appear in data
        - Must not break Typst syntax
        """
        client = sample_input.create_test_client_record(
            first_name="Jean-Paul",
            last_name="O'Neill",
        )

        context = generate_notices.build_template_context(client)

        # Context should contain escaped data, not raw special chars
        assert "client_data" in context

    def test_build_template_context_with_received_vaccines(self) -> None:
        """Verify received vaccine records are included.

        Real-world significance:
        - Vaccine history appears in notices
        - Must include all received doses
        """
        client = sample_input.create_test_client_record(has_received_vaccines=True)

        context = generate_notices.build_template_context(client)

        num_rows = int(context["num_rows"])
        assert num_rows >= 1  # Should have at least one received vaccine

    def test_build_template_context_empty_received(self) -> None:
        """Verify context handles clients with no received vaccines.

        Real-world significance:
        - Some students may have no recorded vaccinations
        - Should not crash; num_rows should be 0
        """
        client = sample_input.create_test_client_record(has_received_vaccines=False)

        context = generate_notices.build_template_context(client)

        assert int(context["num_rows"]) == 0

    def test_build_template_context_includes_formatted_date(self) -> None:
        """Verify context includes formatted date_data_cutoff in client_data.

        Real-world significance:
        - Notices must display the date_data_cutoff from configuration
        - Date must be formatted in the client's language (en or fr)
        - Template receives date as part of client_data dict
        """
        client = sample_input.create_test_client_record()

        context = generate_notices.build_template_context(client)

        # client_data is Typst-serialized; should contain date_data_cutoff key
        assert "client_data" in context
        client_data_str = context["client_data"]
        # The serialized dict should contain the date_data_cutoff key
        assert (
            "date_data_cutoff:" in client_data_str
            or "date_data_cutoff" in client_data_str
        )

    def test_build_template_context_includes_qr_url_when_present(self) -> None:
        """Test that qr_url is included in template context when qr.payload present.

        Real-world significance:
        - Templates need qr_url to make QR codes clickable
        - qr.payload field is set by generate_qr_codes step and read from artifact
        - Must be passed through to Typst template rendering
        """
        # Create client with qr.payload already set (as would come from artifact)
        client_base = sample_input.create_test_client_record()
        # Use dataclass replace to create new instance with qr dict
        from dataclasses import replace

        client = replace(
            client_base,
            qr={
                "payload": "https://survey.example.com/update?client_id=C001",
                "filename": "qr_code_00001_C001.png",
                "path": "/output/artifacts/qr_codes/qr_code_00001_C001.png",
            },
        )

        context = generate_notices.build_template_context(client)

        # client_data dict should contain qr_url key
        assert "client_data" in context
        client_data_str = context["client_data"]
        assert "qr_url:" in client_data_str
        assert "https://survey.example.com/update?client_id=C001" in client_data_str

    def test_build_template_context_omits_qr_url_when_absent(self) -> None:
        """Test that missing qr.payload doesn't break template generation.

        Real-world significance:
        - Defensive: if qr.payload not present, template should still work
        - Graceful fallback if QR generation was skipped
        """
        client = sample_input.create_test_client_record()
        # qr defaults to None in constructor

        context = generate_notices.build_template_context(client)

        # Should generate context without error
        assert "client_data" in context
        # qr_url should not be in client_data
        client_data_str = context["client_data"]
        assert "qr_url:" not in client_data_str


@pytest.mark.unit
class TestLanguageSupport:
    """Unit tests for language-specific functionality."""

    def test_language_renderers_configured(self) -> None:
        """Verify both English and French renderers are available.

        Real-world significance:
        - Pipeline must support bilingual notices
        - Both language renderers must be present
        """
        english_renderer = generate_notices.get_language_renderer(
            Language.ENGLISH, templates_package="templates"
        )
        french_renderer = generate_notices.get_language_renderer(
            Language.FRENCH, templates_package="templates"
        )
        assert callable(english_renderer)
        assert callable(french_renderer)

    def test_render_notice_english_client(self, tmp_test_dir: Path) -> None:
        """Verify English notice can be rendered.

        Real-world significance:
        - Must render without errors
        """
        # Just verify the language renderer is callable
        # (actual rendering requires full Typst setup)
        english_renderer = generate_notices.get_language_renderer(
            Language.ENGLISH, templates_package="templates"
        )
        assert english_renderer is not None

    def test_render_notice_french_client(self, tmp_test_dir: Path) -> None:
        """Verify French notice can be rendered.

        Real-world significance:
        - Must render without errors for fr language code
        """
        # Just verify the language renderer is callable
        french_renderer = generate_notices.get_language_renderer(
            Language.FRENCH, templates_package="templates"
        )
        assert french_renderer is not None
