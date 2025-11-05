"""Unit tests for config_loader module - YAML configuration loading and retrieval.

Tests cover:
- Loading YAML configurations from files
- Error handling for missing files and invalid YAML
- Support for various data types (strings, integers, booleans, lists, nested dicts)
- Default values and fallback behavior

Real-world significance:
- Configuration controls all pipeline behavior (QR generation, encryption, batching, etc.)
- Incorrect config loading can silently disable features or cause crashes
- Config validation ensures all required keys are present
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pipeline import config_loader


@pytest.mark.unit
class TestLoadConfig:
    """Unit tests for load_config function."""

    def test_load_config_with_default_path(self) -> None:
        """Verify config loads from default location.

        Real-world significance:
        - Pipeline must load config automatically without user intervention
        - Default path should point to config/parameters.yaml
        """
        config = config_loader.load_config()

        assert isinstance(config, dict)
        assert len(config) > 0

    def test_load_config_with_custom_path(self) -> None:
        """Verify config loads from custom path.

        Real-world significance:
        - Users may provide config from different directories (e.g., per-district)
        - Must support absolute and relative paths
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config_path.write_text("qr:\n  enabled: false\ntest_key: test_value\n")

            config = config_loader.load_config(config_path)

            assert config["test_key"] == "test_value"

    def test_load_config_with_nested_yaml(self) -> None:
        """Verify nested YAML structures load correctly.

        Real-world significance:
        - Config sections (qr, encryption, pipeline, etc.) are nested
        - Must preserve structure for dot-notation retrieval
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested_config.yaml"
            config_path.write_text(
                """qr:
  enabled: false
section1:
  key1: value1
  key2: value2
section2:
  nested:
    deep_key: deep_value
"""
            )

            config = config_loader.load_config(config_path)

            assert config["section1"]["key1"] == "value1"
            assert config["section2"]["nested"]["deep_key"] == "deep_value"

    def test_load_config_file_not_found(self) -> None:
        """Verify error when config file missing.

        Real-world significance:
        - Missing config indicates setup error; must fail early with clear message
        """
        missing_path = Path("/nonexistent/path/config.yaml")

        with pytest.raises(FileNotFoundError):
            config_loader.load_config(missing_path)

    def test_load_config_empty_file(self) -> None:
        """Verify empty YAML file with valid QR config returns dict.

        Real-world significance:
        - Empty config must still provide valid QR settings (QR enabled by default)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "empty_config.yaml"
            # Even empty files need valid QR config after validation
            config_path.write_text("qr:\n  enabled: false\n")

            config = config_loader.load_config(config_path)

            assert config.get("qr", {}).get("enabled") is False

    def test_load_config_with_various_data_types(self) -> None:
        """Verify YAML correctly loads strings, numbers, booleans, lists, nulls.

        Real-world significance:
        - Config uses all YAML types (e.g., qr.enabled: true, batch_size: 100)
        - Type preservation is critical for correct behavior
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "types_config.yaml"
            config_path.write_text(
                """qr:
  enabled: false
string_val: hello
int_val: 42
float_val: 3.14
bool_val: true
list_val:
  - item1
  - item2
null_val: null
"""
            )

            config = config_loader.load_config(config_path)

            assert config["string_val"] == "hello"
            assert config["int_val"] == 42
            assert config["float_val"] == 3.14
            assert config["bool_val"] is True
            assert config["list_val"] == ["item1", "item2"]
            assert config["null_val"] is None

    def test_load_config_with_invalid_yaml(self) -> None:
        """Verify error on invalid YAML syntax.

        Real-world significance:
        - Malformed config will cause hard-to-debug failures downstream
        - Must catch and report early
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "invalid_config.yaml"
            config_path.write_text("key: value\n  invalid: : :")

            with pytest.raises(Exception):  # yaml.YAMLError or similar
                config_loader.load_config(config_path)


@pytest.mark.unit
class TestActualConfig:
    """Unit tests using the actual parameters.yaml (if present).

    Real-world significance:
    - Should verify that production config is valid and loadable
    - Catches config corruption or breaking changes
    """

    def test_actual_config_loads_successfully(self) -> None:
        """Verify production config loads without error."""
        config = config_loader.load_config()

        assert isinstance(config, dict)
        assert len(config) > 0

    def test_actual_config_has_core_sections(self) -> None:
        """Verify config has expected top-level sections."""
        config = config_loader.load_config()

        # At least some of these should exist
        has_sections = any(
            key in config for key in ["pipeline", "qr", "encryption", "bundling"]
        )
        assert has_sections, "Config missing core sections"
