"""Tests for QR code generation module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts import generate_qr_codes


class TestLoadQrSettings:
    """Tests for load_qr_settings function."""

    def test_load_qr_settings_with_valid_template(self):
        """Test loading valid QR settings from config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "qr": {
                    "payload_template": "https://example.com?id={client_id}&lang={language_code}"
                },
                "delivery_date": "2025-04-08",
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            template, delivery_date = generate_qr_codes.load_qr_settings(temp_path)
            assert (
                template == "https://example.com?id={client_id}&lang={language_code}"
            )
            assert delivery_date == "2025-04-08"
        finally:
            temp_path.unlink()

    def test_load_qr_settings_missing_template_raises_error(self):
        """Test that missing payload_template raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {"qr": {"enabled": True}}
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                generate_qr_codes.load_qr_settings(temp_path)
            assert "qr.payload_template is not specified" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_load_qr_settings_template_not_string_raises_error(self):
        """Test that non-string payload_template raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {"qr": {"payload_template": {"en": "url"}}}
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                generate_qr_codes.load_qr_settings(temp_path)
            assert "must be a string" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_load_qr_settings_missing_config_file_raises_error(self):
        """Test that missing config file raises FileNotFoundError."""
        nonexistent_path = Path("/nonexistent/path/config.yaml")
        with pytest.raises(FileNotFoundError):
            generate_qr_codes.load_qr_settings(nonexistent_path)

    def test_load_qr_settings_without_delivery_date(self):
        """Test loading settings when delivery_date is not present."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "qr": {"payload_template": "https://example.com?id={client_id}"}
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            template, delivery_date = generate_qr_codes.load_qr_settings(temp_path)
            assert template == "https://example.com?id={client_id}"
            assert delivery_date is None
        finally:
            temp_path.unlink()


class TestBuildQrContext:
    """Tests for _build_qr_context function."""

    def test_build_qr_context_en_language(self):
        """Test building QR context with English language code."""
        context = generate_qr_codes._build_qr_context(
            client_id="12345",
            first_name="John",
            last_name="Doe",
            dob_display="Jan 1, 2020",
            dob_iso="2020-01-01",
            school="Test School",
            city="Toronto",
            postal_code="M1A1A1",
            province="ON",
            street_address="123 Main St",
            language_code="en",
            delivery_date="2025-04-08",
        )

        assert context["client_id"] == "12345"
        assert context["first_name"] == "John"
        assert context["last_name"] == "Doe"
        assert context["name"] == "John Doe"
        assert context["language"] == "english"
        assert context["language_code"] == "en"
        assert context["date_of_birth"] == "Jan 1, 2020"
        assert context["date_of_birth_iso"] == "2020-01-01"
        assert context["delivery_date"] == "2025-04-08"

    def test_build_qr_context_fr_language(self):
        """Test building QR context with French language code."""
        context = generate_qr_codes._build_qr_context(
            client_id="12345",
            first_name="Jean",
            last_name="Dupont",
            dob_display="1 jan 2020",
            dob_iso="2020-01-01",
            school="École Test",
            city="Montréal",
            postal_code="H1A1A1",
            province="QC",
            street_address="123 Rue Principale",
            language_code="fr",
            delivery_date="2025-04-08",
        )

        assert context["language"] == "french"
        assert context["language_code"] == "fr"

    def test_build_qr_context_handles_none_values(self):
        """Test that _build_qr_context safely handles None values."""
        context = generate_qr_codes._build_qr_context(
            client_id="12345",
            first_name="",
            last_name="",
            dob_display="",
            dob_iso=None,
            school="",
            city="",
            postal_code="",
            province="",
            street_address="",
            language_code="en",
            delivery_date=None,
        )

        assert context["client_id"] == "12345"
        assert context["first_name"] == ""
        assert context["name"] == ""
        assert context["date_of_birth_iso"] == ""
        assert context["delivery_date"] == ""


class TestFormatQrPayload:
    """Tests for _format_qr_payload function."""

    def test_format_qr_payload_valid_template(self):
        """Test formatting valid QR payload."""
        template = "https://example.com?id={client_id}&name={name}&lang={language_code}"
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
            "language": "english",
            "delivery_date": "2025-04-08",
        }

        payload = generate_qr_codes._format_qr_payload(template, context)
        assert payload == "https://example.com?id=12345&name=John Doe&lang=en"

    def test_format_qr_payload_missing_placeholder_raises_error(self):
        """Test that missing placeholder in context raises KeyError."""
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
            "language": "english",
            "delivery_date": "2025-04-08",
        }

        with pytest.raises(KeyError):
            generate_qr_codes._format_qr_payload(template, context)

    def test_format_qr_payload_disallowed_placeholder_raises_error(self):
        """Test that disallowed placeholder raises ValueError."""
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
            "language": "english",
            "delivery_date": "2025-04-08",
        }

        with pytest.raises(ValueError) as exc_info:
            generate_qr_codes._format_qr_payload(template, context)
        assert "Disallowed placeholder" in str(exc_info.value)


class TestGenerateQrCodes:
    """Tests for generate_qr_codes function."""

    @pytest.fixture
    def sample_artifact(self, tmp_path):
        """Create a sample preprocessed artifact."""
        artifact = {
            "run_id": "20251023T200355",
            "language": "en",
            "total_clients": 2,
            "warnings": [],
            "clients": [
                {
                    "sequence": 1,
                    "client_id": "1001",
                    "person": {
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "date_of_birth_iso": "2020-01-15",
                        "date_of_birth_display": "Jan 15, 2020",
                    },
                    "school": {"name": "Primary School"},
                    "contact": {
                        "city": "Toronto",
                        "postal_code": "M1A1A1",
                        "province": "ON",
                        "street": "123 Main St",
                    },
                },
                {
                    "sequence": 2,
                    "client_id": "1002",
                    "person": {
                        "first_name": "Bob",
                        "last_name": "Jones",
                        "date_of_birth_iso": "2019-06-20",
                        "date_of_birth_display": "Jun 20, 2019",
                    },
                    "school": {"name": "Primary School"},
                    "contact": {
                        "city": "Toronto",
                        "postal_code": "M1A1A1",
                        "province": "ON",
                        "street": "456 Oak Ave",
                    },
                },
            ],
        }

        artifact_path = tmp_path / "preprocessed_clients_test.json"
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
        return artifact_path

    @pytest.fixture
    def config_with_template(self, tmp_path):
        """Create a config file with QR template."""
        config = {
            "qr": {
                "enabled": True,
                "payload_template": "https://example.com/update?id={client_id}&lang={language_code}",
            },
            "delivery_date": "2025-04-08",
        }
        config_path = tmp_path / "parameters.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        return config_path

    def test_generate_qr_codes_creates_files(self, sample_artifact, config_with_template):
        """Test that generate_qr_codes creates PNG files."""
        output_dir = sample_artifact.parent / "output"
        output_dir.mkdir(exist_ok=True)

        with patch("scripts.generate_qr_codes.generate_qr_code") as mock_gen:
            mock_gen.return_value = Path("dummy.png")

            result = generate_qr_codes.generate_qr_codes(
                sample_artifact, output_dir, config_with_template
            )

            # Should have called generate_qr_code twice (once per client)
            assert mock_gen.call_count == 2
            assert len(result) == 2

    def test_generate_qr_codes_without_template_raises_error(self, sample_artifact):
        """Test that missing template raises RuntimeError."""
        config = {"qr": {"enabled": True}}
        config_path = sample_artifact.parent / "parameters.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        output_dir = sample_artifact.parent / "output"
        output_dir.mkdir(exist_ok=True)

        with pytest.raises(RuntimeError) as exc_info:
            generate_qr_codes.generate_qr_codes(
                sample_artifact, output_dir, config_path
            )
        assert "Cannot generate QR codes" in str(exc_info.value)
        assert "payload_template" in str(exc_info.value)

    def test_generate_qr_codes_disabled_returns_empty(self, sample_artifact, tmp_path):
        """Test that disabled QR generation returns empty list."""
        config = {
            "qr": {
                "enabled": False,
                "payload_template": "https://example.com/update?id={client_id}",
            }
        }
        config_path = tmp_path / "parameters.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir(exist_ok=True)

        result = generate_qr_codes.generate_qr_codes(
            sample_artifact, output_dir, config_path
        )
        assert result == []

    def test_generate_qr_codes_no_clients_returns_empty(self, tmp_path):
        """Test that artifact with no clients returns empty list."""
        artifact = {
            "run_id": "20251023T200355",
            "language": "en",
            "total_clients": 0,
            "warnings": [],
            "clients": [],
        }
        artifact_path = tmp_path / "preprocessed_clients_test.json"
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

        config = {
            "qr": {
                "enabled": True,
                "payload_template": "https://example.com/update?id={client_id}",
            }
        }
        config_path = tmp_path / "parameters.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir(exist_ok=True)

        result = generate_qr_codes.generate_qr_codes(
            artifact_path, output_dir, config_path
        )
        assert result == []
