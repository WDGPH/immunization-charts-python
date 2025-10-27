"""Tests for configuration validation across pipeline steps.

This module tests the validate_config() function which ensures that
required configuration keys are present and valid when config is loaded.

Real-world significance:
- Validates conditional requirements (e.g., qr.payload_template if qr.enabled=true)
- Catches configuration errors early at load time with clear error messages
- Prevents cryptic failures deep in pipeline execution
- Helps administrators debug configuration issues

Note: Since validate_config() validates the entire config, test configs must have
valid QR settings (enabled=false or with payload_template) to focus testing on
other sections like batching or typst.
"""

from __future__ import annotations

import pytest
from typing import Dict, Any

from pipeline.config_loader import validate_config


# Minimal valid config for sections not being tested
MINIMAL_VALID_CONFIG: Dict[str, Any] = {
    "qr": {"enabled": False},  # QR disabled, no template required
}


@pytest.mark.unit
class TestQRConfigValidation:
    """Test configuration validation for QR Code Generation."""

    def test_qr_validation_passes_when_disabled(self) -> None:
        """QR validation should pass when qr.enabled=false (no template required)."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": False,
                # Template not required when disabled
            }
        }
        # Should not raise
        validate_config(config)

    def test_qr_validation_passes_with_valid_template(self) -> None:
        """QR validation should pass when enabled with valid template."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": True,
                "payload_template": "https://example.com/update?id={client_id}",
            }
        }
        # Should not raise
        validate_config(config)

    def test_qr_validation_fails_when_enabled_but_no_template(self) -> None:
        """QR validation should fail when enabled=true but template is missing."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": True,
                # Template is missing
            }
        }
        with pytest.raises(ValueError, match="qr.payload_template"):
            validate_config(config)

    def test_qr_validation_fails_when_enabled_but_empty_template(self) -> None:
        """QR validation should fail when enabled=true but template is empty string."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": True,
                "payload_template": "",  # Empty string
            }
        }
        with pytest.raises(ValueError, match="qr.payload_template"):
            validate_config(config)

    def test_qr_validation_fails_when_template_not_string(self) -> None:
        """QR validation should fail when template is not a string."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": True,
                "payload_template": 12345,  # Invalid: not a string
            }
        }
        with pytest.raises(ValueError, match="must be a string"):
            validate_config(config)

    def test_qr_validation_fails_when_template_is_list(self) -> None:
        """QR validation should fail when template is a list."""
        config: Dict[str, Any] = {
            "qr": {
                "enabled": True,
                "payload_template": ["url1", "url2"],  # Invalid: list
            }
        }
        with pytest.raises(ValueError, match="must be a string"):
            validate_config(config)

    def test_qr_validation_uses_default_enabled_true(self) -> None:
        """QR validation should default qr.enabled=true (requires template)."""
        config: Dict[str, Any] = {
            "qr": {
                # enabled not specified, defaults to true
            }
        }
        with pytest.raises(ValueError, match="qr.payload_template"):
            validate_config(config)

    def test_qr_validation_handles_missing_qr_section(self) -> None:
        """QR validation should handle missing qr section (defaults enabled=true)."""
        config: Dict[str, Any] = {
            # No qr section at all
        }
        with pytest.raises(ValueError, match="qr.payload_template"):
            validate_config(config)


@pytest.mark.unit
class TestTypstConfigValidation:
    """Test configuration validation for Typst Compilation."""

    def test_typst_validation_passes_with_defaults(self) -> None:
        """Typst validation should pass when using default bin."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "typst": {},  # No explicit bin, uses default "typst"
        }
        # Should not raise
        validate_config(config)

    def test_typst_validation_passes_with_valid_bin(self) -> None:
        """Typst validation should pass with valid bin string."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "typst": {
                "bin": "typst",
                "font_path": "/path/to/fonts",
            },
        }
        # Should not raise
        validate_config(config)

    def test_typst_validation_fails_when_bin_not_string(self) -> None:
        """Typst validation should fail when bin is not a string."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "typst": {
                "bin": 12345,  # Invalid: not a string
            },
        }
        with pytest.raises(ValueError, match="typst.bin must be a string"):
            validate_config(config)

    def test_typst_validation_fails_when_bin_is_list(self) -> None:
        """Typst validation should fail when bin is a list."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "typst": {
                "bin": ["/usr/bin/typst"],  # Invalid: list
            },
        }
        with pytest.raises(ValueError, match="typst.bin must be a string"):
            validate_config(config)


@pytest.mark.unit
class TestBatchingConfigValidation:
    """Test configuration validation for PDF Batching."""

    def test_batching_validation_passes_when_disabled(self) -> None:
        """Batching validation should pass when batch_size=0 (disabled)."""
        config: Dict[str, Any] = {
            "qr": {"enabled": False},  # QR must be valid for overall validation
            "batching": {
                "batch_size": 0,  # Disabled
            },
        }
        # Should not raise
        validate_config(config)

    def test_batching_validation_passes_with_valid_size_and_strategy(self) -> None:
        """Batching validation should pass with valid batch_size and group_by."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 100,
                "group_by": "school",
            },
        }
        # Should not raise
        validate_config(config)

    def test_batching_validation_passes_with_null_group_by(self) -> None:
        """Batching validation should pass with null group_by (sequential batching)."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 50,
                "group_by": None,
            },
        }
        # Should not raise
        validate_config(config)

    def test_batching_validation_fails_when_size_not_integer(self) -> None:
        """Batching validation should fail when batch_size is not an integer."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": "100",  # Invalid: string instead of int
            },
        }
        with pytest.raises(ValueError, match="batch_size must be an integer"):
            validate_config(config)

    def test_batching_validation_fails_when_size_negative(self) -> None:
        """Batching validation should fail when batch_size is negative."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": -100,  # Invalid: negative
            },
        }
        with pytest.raises(ValueError, match="batch_size must be positive"):
            validate_config(config)

    def test_batching_validation_fails_with_invalid_group_by(self) -> None:
        """Batching validation should fail when group_by is invalid strategy."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 100,
                "group_by": "invalid_strategy",  # Invalid: not in BatchStrategy enum
            },
        }
        with pytest.raises(ValueError, match="group_by"):
            validate_config(config)

    def test_batching_validation_fails_when_size_positive_but_not_integer(self) -> None:
        """Batching validation should fail when batch_size is float."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 100.5,  # Invalid: float, not int
            },
        }
        with pytest.raises(ValueError, match="batch_size must be an integer"):
            validate_config(config)

    def test_batching_validation_passes_with_board_group_by(self) -> None:
        """Batching validation should pass with valid group_by='board'."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 100,
                "group_by": "board",
            },
        }
        # Should not raise
        validate_config(config)

    def test_batching_validation_passes_with_size_group_by(self) -> None:
        """Batching validation should pass with valid group_by='size'."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {
                "batch_size": 100,
                "group_by": "size",
            },
        }
        # Should not raise
        validate_config(config)

    def test_batching_validation_handles_missing_batching_section(self) -> None:
        """Batching validation should handle missing batching section (defaults batch_size=0)."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            # No batching section; will use defaults
        }
        # Should not raise (batch_size defaults to 0, which is disabled)
        validate_config(config)


@pytest.mark.unit
class TestConditionalValidationLogic:
    """Test that validation correctly handles conditional requirements."""

    def test_qr_payload_required_only_when_enabled(self) -> None:
        """Payload is only required when qr.enabled is explicitly true."""
        # Case 1: enabled=false, no template required
        config1: Dict[str, Any] = {"qr": {"enabled": False}}
        validate_config(config1)  # Should pass

        # Case 2: enabled=true, template required
        config2: Dict[str, Any] = {"qr": {"enabled": True}}
        with pytest.raises(ValueError, match="payload_template"):
            validate_config(config2)  # Should fail

        # Case 3: not specified, defaults to enabled=true, template required
        config3: Dict[str, Any] = {"qr": {}}
        with pytest.raises(ValueError, match="payload_template"):
            validate_config(config3)  # Should fail

    def test_group_by_validated_only_when_batching_enabled(self) -> None:
        """group_by is only validated when batch_size > 0."""
        # Case 1: batch_size=0, group_by not validated even if invalid
        config1: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {"batch_size": 0, "group_by": "invalid"},
        }
        validate_config(config1)  # Should pass (batch_size=0 disables batching)

        # Case 2: batch_size > 0, group_by is validated
        config2: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {"batch_size": 100, "group_by": "invalid"},
        }
        with pytest.raises(ValueError, match="group_by"):
            validate_config(config2)  # Should fail (invalid strategy)


@pytest.mark.unit
class TestErrorMessages:
    """Test that error messages are clear and actionable."""

    def test_qr_error_message_includes_config_key(self) -> None:
        """Error message should include config key and clear action."""
        config: Dict[str, Any] = {"qr": {"enabled": True}}
        with pytest.raises(ValueError) as exc_info:
            validate_config(config)

        error_msg = str(exc_info.value)
        # Check message includes key information
        assert "qr.payload_template" in error_msg
        assert "not specified" in error_msg or "not found" in error_msg
        # Check message includes action
        assert "define" in error_msg.lower() or "set" in error_msg.lower()

    def test_batching_error_message_includes_strategy_options(self) -> None:
        """Error message should include information about valid strategies."""
        config: Dict[str, Any] = {
            **MINIMAL_VALID_CONFIG,
            "batching": {"batch_size": 100, "group_by": "invalid"},
        }
        with pytest.raises(ValueError) as exc_info:
            validate_config(config)

        error_msg = str(exc_info.value)
        # Error should mention the invalid value or strategy
        assert "group_by" in error_msg or "strategy" in error_msg
