"""Unit tests for generate_qr_codes module - QR code generation.

Tests cover:
- QR code generation for client payloads
- Filename generation and path handling
- Configuration-driven QR generation control
- Payload template formatting and validation
- Error handling for invalid inputs
- Language support (en/fr)

Real-world significance:
- Step 3 of pipeline: generates QR codes linking to immunization records
- QR codes enable fast lookup of student notices from PDF
- Must handle both enabled and disabled states (config-driven)
- Payload templates are configurable for different deployment scenarios
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pipeline import generate_qr_codes, utils as pipeline_utils
from tests.fixtures import sample_input


@pytest.mark.unit
class TestLoadQrSettings:
    """Unit tests for load_qr_settings function."""

    def test_load_qr_settings_with_valid_template(self, tmp_test_dir: Path) -> None:
        """Verify valid QR settings load successfully.

        Real-world significance:
        - Production config should contain complete QR settings
        - Template must be a string (not dict or list)
        """
        config_path = tmp_test_dir / "config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "qr": {
                        "payload_template": "https://example.com/update?client_id={client_id}"
                    },
                    "date_notice_delivery": "2025-04-08",
                }
            )
        )

        template, date_notice_delivery = generate_qr_codes.load_qr_settings(config_path)

        assert template == "https://example.com/update?client_id={client_id}"
        assert date_notice_delivery == "2025-04-08"

    def test_load_qr_settings_missing_template_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when payload_template is missing from config.

        Real-world significance:
        - Configuration error: QR enabled but no template defined
        - Must fail early with clear guidance
        """
        config_path = tmp_test_dir / "config.yaml"
        config_path.write_text(yaml.dump({"qr": {"enabled": True}}))

        with pytest.raises(ValueError, match="payload_template"):
            generate_qr_codes.load_qr_settings(config_path)

    def test_load_qr_settings_template_not_string_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error when payload_template is not a string.

        Real-world significance:
        - Configuration error: someone provided dict instead of string
        - Indicates migration from per-language templates (en/fr) to single template
        """
        config_path = tmp_test_dir / "config.yaml"
        config_path.write_text(
            yaml.dump({"qr": {"payload_template": {"en": "url", "fr": "url"}}})
        )

        with pytest.raises(ValueError, match="must be a string"):
            generate_qr_codes.load_qr_settings(config_path)

    def test_load_qr_settings_missing_file_raises_error(self) -> None:
        """Verify error when config file doesn't exist.

        Real-world significance:
        - Config path incorrect or file deleted between steps
        - Must fail fast with clear error
        """
        with pytest.raises(FileNotFoundError):
            generate_qr_codes.load_qr_settings(Path("/nonexistent/config.yaml"))

    def test_load_qr_settings_without_delivery_date(self, tmp_test_dir: Path) -> None:
        """Verify delivery_date is optional.

        Real-world significance:
        - Some deployments may not need delivery_date in QR payloads
        - Should default to None if not provided
        """
        config_path = tmp_test_dir / "config.yaml"
        config_path.write_text(
            yaml.dump(
                {"qr": {"payload_template": "https://example.com?id={client_id}"}}
            )
        )

        template, delivery_date = generate_qr_codes.load_qr_settings(config_path)

        assert template == "https://example.com?id={client_id}"
        assert delivery_date is None


@pytest.mark.unit
class TestFormatQrPayload:
    """Unit tests for format_qr_payload function."""

    def test_format_qr_payload_valid_template(self) -> None:
        """Verify valid template formats correctly.

        Real-world significance:
        - Production URL template with common placeholders
        - Must interpolate all referenced fields
        """
        template = "https://example.com/update?client_id={client_id}&dob={date_of_birth_iso}&lang={language_code}"
        context = {
            "client_id": "12345",
            "name": "John Doe",
            "language_code": "en",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "",
            "date_of_birth_iso": "2020-01-01",
            "school": "School",
            "city": "City",
            "postal_code": "12345",
            "province": "ON",
            "street_address": "St",
            "delivery_date": "2025-04-08",
        }

        payload = pipeline_utils.validate_and_format_template(
            template,
            context,
            allowed_fields=generate_qr_codes.SUPPORTED_QR_TEMPLATE_FIELDS,
        )

        assert "client_id=12345" in payload
        assert "dob=2020-01-01" in payload
        assert "lang=en" in payload

    def test_format_qr_payload_partial_template(self) -> None:
        """Verify partial templates work (only using subset of fields).

        Real-world significance:
        - Simple templates may only need client_id and name
        - Should ignore unused context fields
        """
        template = "https://example.com/update?id={client_id}&name={name}"
        context = {
            "client_id": "12345",
            "name": "John Doe",
            "language_code": "en",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "",
            "date_of_birth_iso": "2020-01-01",
            "school": "School",
            "city": "City",
            "postal_code": "12345",
            "province": "ON",
            "street_address": "St",
            "delivery_date": "2025-04-08",
        }

        payload = pipeline_utils.validate_and_format_template(
            template,
            context,
            allowed_fields=generate_qr_codes.SUPPORTED_QR_TEMPLATE_FIELDS,
        )

        assert payload == "https://example.com/update?id=12345&name=John Doe"

    def test_format_qr_payload_missing_placeholder_raises_error(self) -> None:
        """Verify error when template uses non-existent placeholder.

        Real-world significance:
        - Configuration error in template string
        - Must fail fast, not silently produce bad QR codes
        """
        template = "https://example.com?id={client_id}&missing={nonexistent}"
        context = {
            "client_id": "12345",
            "name": "John Doe",
            "language_code": "en",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "",
            "date_of_birth_iso": "2020-01-01",
            "school": "School",
            "city": "City",
            "postal_code": "12345",
            "province": "ON",
            "street_address": "St",
            "delivery_date": "2025-04-08",
        }

        with pytest.raises(KeyError):
            pipeline_utils.validate_and_format_template(
                template,
                context,
                allowed_fields=generate_qr_codes.SUPPORTED_QR_TEMPLATE_FIELDS,
            )

    def test_format_qr_payload_disallowed_placeholder_raises_error(self) -> None:
        """Verify error when template uses disallowed placeholder.

        Real-world significance:
        - Security guard against accidental leakage of sensitive data
        - Only allowed fields can appear in QR payloads
        """
        template = "https://example.com?id={client_id}&secret={secret_field}"
        context = {
            "client_id": "12345",
            "secret_field": "should_not_work",
            "name": "John Doe",
            "language_code": "en",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "",
            "date_of_birth_iso": "2020-01-01",
            "school": "School",
            "city": "City",
            "postal_code": "12345",
            "province": "ON",
            "street_address": "St",
            "delivery_date": "2025-04-08",
        }

        with pytest.raises(ValueError, match="Disallowed"):
            pipeline_utils.validate_and_format_template(
                template,
                context,
                allowed_fields=generate_qr_codes.SUPPORTED_QR_TEMPLATE_FIELDS,
            )

    def test_format_qr_payload_empty_placeholder_value(self) -> None:
        """Verify empty placeholder values are handled.

        Real-world significance:
        - Missing field should produce empty string in URL (e.g., ?school=)
        - Should not crash or skip the placeholder
        """
        template = "https://example.com?client={client_id}&school={school}"
        context = {
            "client_id": "12345",
            "school": "",
            "name": "John Doe",
            "language_code": "en",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "",
            "date_of_birth_iso": "2020-01-01",
            "city": "City",
            "postal_code": "12345",
            "province": "ON",
            "street_address": "St",
            "delivery_date": "2025-04-08",
        }

        payload = pipeline_utils.validate_and_format_template(
            template,
            context,
            allowed_fields=generate_qr_codes.SUPPORTED_QR_TEMPLATE_FIELDS,
        )

        assert "client=12345" in payload
        assert "school=" in payload


@pytest.mark.unit
class TestGenerateQrCodes:
    """Unit tests for generate_qr_codes orchestration function."""

    def test_generate_qr_codes_disabled_returns_empty(
        self, tmp_output_structure
    ) -> None:
        """Verify QR generation skipped when disabled in config.

        Real-world significance:
        - Administrator can disable QR codes in parameters.yaml
        - Pipeline should silently skip and continue
        """
        # Create artifact
        artifact = sample_input.create_test_artifact_payload(
            num_clients=2, language="en"
        )
        artifact_path = tmp_output_structure["artifacts"] / "preprocessed.json"
        sample_input.write_test_artifact(artifact, tmp_output_structure["artifacts"])

        # Disable QR generation
        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {"qr": {"enabled": False, "payload_template": "https://example.com"}}
        config_path.write_text(yaml.dump(config))

        result = generate_qr_codes.generate_qr_codes(
            artifact_path.parent
            / f"preprocessed_clients_{artifact.run_id}_{artifact.language}.json",
            tmp_output_structure["root"],
            config_path,
        )

        assert result == []

    def test_generate_qr_codes_no_clients_returns_empty(
        self, tmp_output_structure
    ) -> None:
        """Verify empty list returned when artifact has no clients.

        Real-world significance:
        - Data extraction yielded no matching students
        - Should complete without errors
        """
        artifact = {
            "run_id": "test_001",
            "language": "en",
            "total_clients": 0,
            "warnings": [],
            "clients": [],
        }
        artifact_path = tmp_output_structure["artifacts"] / "preprocessed.json"
        artifact_path.write_text(json.dumps(artifact))

        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {
            "qr": {
                "enabled": True,
                "payload_template": "https://example.com?id={client_id}",
            }
        }
        config_path.write_text(yaml.dump(config))

        result = generate_qr_codes.generate_qr_codes(
            artifact_path,
            tmp_output_structure["root"],
            config_path,
        )

        assert result == []

    def test_generate_qr_codes_creates_subdirectory(self, tmp_output_structure) -> None:
        """Verify qr_codes subdirectory is created.

        Real-world significance:
        - First pipeline run: directory structure doesn't exist yet
        - Should auto-create qr_codes/ subdirectory
        """
        artifact = sample_input.create_test_artifact_payload(num_clients=1)
        artifact_path = tmp_output_structure["artifacts"] / "preprocessed.json"
        sample_input.write_test_artifact(artifact, tmp_output_structure["artifacts"])

        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {
            "qr": {
                "enabled": True,
                "payload_template": "https://example.com?id={client_id}",
            }
        }
        config_path.write_text(yaml.dump(config))

        qr_output_dir = tmp_output_structure["root"] / "qr_codes"
        assert not qr_output_dir.exists()

        with patch("pipeline.generate_qr_codes.generate_qr_code") as mock_gen:
            mock_gen.return_value = Path("dummy.png")
            generate_qr_codes.generate_qr_codes(
                artifact_path.parent
                / f"preprocessed_clients_{artifact.run_id}_{artifact.language}.json",
                tmp_output_structure["root"],
                config_path,
            )

        assert qr_output_dir.exists()

    def test_generate_qr_codes_missing_template_raises_error(
        self, tmp_output_structure
    ) -> None:
        """Verify error when QR enabled but template missing.

        Real-world significance:
        - Configuration error: qr.enabled=true but no template provided
        - Must fail fast with clear guidance (at config load time)
        """
        artifact = sample_input.create_test_artifact_payload(num_clients=1)
        artifact_path = tmp_output_structure["artifacts"] / "preprocessed.json"
        sample_input.write_test_artifact(artifact, tmp_output_structure["artifacts"])

        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {"qr": {"enabled": True}}
        config_path.write_text(yaml.dump(config))

        with pytest.raises(ValueError, match="qr.payload_template"):
            generate_qr_codes.generate_qr_codes(
                artifact_path.parent
                / f"preprocessed_clients_{artifact.run_id}_{artifact.language}.json",
                tmp_output_structure["root"],
                config_path,
            )
