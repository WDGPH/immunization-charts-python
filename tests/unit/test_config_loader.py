"""Unit tests for config_loader module - YAML configuration loading and retrieval.

Tests cover:
- Loading YAML configurations from files
- Retrieving nested values with dot notation
- Error handling for missing files and invalid YAML
- Support for various data types (strings, integers, booleans, lists, nested dicts)
- Default values and fallback behavior

Real-world significance:
- Configuration controls all pipeline behavior (QR generation, encryption, batching, etc.)
- Incorrect config loading can silently disable features or cause crashes
- Dot notation retrieval enables simple config access throughout codebase
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

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
            config_path.write_text("test_key: test_value\n")

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
                """section1:
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
        """Verify empty YAML file returns empty dict.

        Real-world significance:
        - Should gracefully handle empty config (allows progressive setup)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "empty_config.yaml"
            config_path.write_text("")

            config = config_loader.load_config(config_path)

            assert config == {}

    def test_load_config_with_various_data_types(self) -> None:
        """Verify YAML correctly loads strings, numbers, booleans, lists, nulls.

        Real-world significance:
        - Config uses all YAML types (e.g., qr.enabled: true, batch_size: 100)
        - Type preservation is critical for correct behavior
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "types_config.yaml"
            config_path.write_text(
                """string_val: hello
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
class TestGetConfigValue:
    """Unit tests for get_config_value function with dot notation."""

    def test_get_config_value_single_key(self) -> None:
        """Verify single-level key retrieval.

        Real-world significance:
        - Used throughout codebase to access top-level config values
        """
        config = {"key": "value"}

        result = config_loader.get_config_value(config, "key")

        assert result == "value"

    def test_get_config_value_nested_with_dot_notation(self) -> None:
        """Verify dot notation retrieves nested values.

        Real-world significance:
        - Used to access qr.enabled, encryption.password.template, etc.
        - Cleaner and safer than nested bracket access
        """
        config = {"section": {"subsection": {"key": "nested_value"}}}

        result = config_loader.get_config_value(config, "section.subsection.key")

        assert result == "nested_value"

    def test_get_config_value_missing_key_returns_default(self) -> None:
        """Verify missing key returns default value.

        Real-world significance:
        - Allows graceful degradation when optional config keys are missing
        - Prevents KeyError crashes in pipeline
        """
        config = {"existing": "value"}

        result = config_loader.get_config_value(config, "missing", default="default")

        assert result == "default"

    def test_get_config_value_missing_key_returns_none(self) -> None:
        """Verify missing key returns None when no default provided.

        Real-world significance:
        - Distinguishes between "key missing" and "key has value None"
        - Caller can use None to detect missing optional config
        """
        config = {"existing": "value"}

        result = config_loader.get_config_value(config, "missing")

        assert result is None

    def test_get_config_value_missing_intermediate_key(self) -> None:
        """Verify missing intermediate key path returns default.

        Real-world significance:
        - e.g., config missing encryption.password.template should not crash
        - Must safely handle partial config structures
        """
        config = {"section": {"key": "value"}}

        result = config_loader.get_config_value(
            config, "section.missing.key", default="fallback"
        )

        assert result == "fallback"

    def test_get_config_value_non_dict_intermediate(self) -> None:
        """Verify accessing nested keys on non-dict returns default.

        Real-world significance:
        - Config corruption (wrong type) shouldn't crash pipeline
        - Must gracefully fall back
        """
        config = {"section": "not_a_dict"}

        result = config_loader.get_config_value(
            config, "section.key", default="fallback"
        )

        assert result == "fallback"

    def test_get_config_value_empty_config(self) -> None:
        """Verify retrieving from empty config returns default.

        Real-world significance:
        - Must handle edge case of completely empty config
        """
        config: Dict[str, Any] = {}

        result = config_loader.get_config_value(config, "any.key", default="default")

        assert result == "default"

    def test_get_config_value_with_none_values_uses_default(self) -> None:
        """Verify keys with None values return default (falsy handling).

        Real-world significance:
        - config: {section: {key: null}} should use default, not return None
        - None often indicates "not configured", so default is more appropriate
        """
        config = {"section": {"key": None}}

        result = config_loader.get_config_value(
            config, "section.key", default="default"
        )

        assert result == "default"

    def test_get_config_value_with_falsy_values_returns_value(self) -> None:
        """Verify that falsy but valid values (0, False, empty string) are returned.

        Real-world significance:
        - batch_size: 0 or qr.enabled: false are valid configurations
        - Must distinguish between "missing" and "falsy but present"
        """
        config = {
            "zero": 0,
            "false": False,
            "empty_string": "",
            "nested": {
                "zero": 0,
                "false": False,
            },
        }

        assert config_loader.get_config_value(config, "zero") == 0
        assert config_loader.get_config_value(config, "false") is False
        assert config_loader.get_config_value(config, "empty_string") == ""
        assert config_loader.get_config_value(config, "nested.zero") == 0
        assert config_loader.get_config_value(config, "nested.false") is False

    def test_get_config_value_with_list_values(self) -> None:
        """Verify list values are retrieved correctly.

        Real-world significance:
        - chart_diseases_header and ignore_agents are lists in config
        - Must preserve list structure
        """
        config = {"items": ["a", "b", "c"], "nested": {"items": [1, 2, 3]}}

        items = config_loader.get_config_value(config, "items")
        assert items == ["a", "b", "c"]

        nested_items = config_loader.get_config_value(config, "nested.items")
        assert nested_items == [1, 2, 3]


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
            key in config for key in ["pipeline", "qr", "encryption", "batching"]
        )
        assert has_sections, "Config missing core sections"
