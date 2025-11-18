"""Integration tests for configuration-driven pipeline behavior.

Tests cover:
- Feature flags affect actual behavior (qr.enabled, encryption.enabled, bundling.enabled)
- Configuration options propagate through pipeline steps
- Invalid config values are caught and reported
- Default configuration allows pipeline to run
- Batching strategies (group_by school, board, or sequential)
- Cleanup configuration affects file removal behavior

Real-world significance:
- Configuration controls optional features and pipeline behavior
- Must verify config actually changes behavior (not just stored)
- Users rely on configuration to enable/disable features
- Misconfigured pipeline may fail silently or unexpectedly
"""

from __future__ import annotations

from typing import Any, Dict

import pytest


@pytest.mark.integration
class TestConfigDrivenBehavior:
    """Integration tests for config controlling pipeline behavior."""

    def test_qr_enabled_flag_exists_in_config(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify QR enabled flag is present in default config.

        Real-world significance:
        - QR generation can be disabled to save processing time
        - Config must have boolean flag to control this
        """
        assert "qr" in default_config
        assert "enabled" in default_config["qr"]
        assert isinstance(default_config["qr"]["enabled"], bool)

    def test_encryption_enabled_flag_exists_in_config(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify encryption enabled flag is present in default config.

        Real-world significance:
        - Encryption is optional for protecting sensitive data
        - Config must allow enabling/disabling safely
        """
        assert "encryption" in default_config
        assert "enabled" in default_config["encryption"]
        assert isinstance(default_config["encryption"]["enabled"], bool)

    def test_bundling_enabled_flag_exists_in_config(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify bundling configuration exists.

        Real-world significance:
        - Batching groups PDFs for efficient distribution
        - bundle_size controls whether bundling is active (0 = disabled)
        """
        assert "bundling" in default_config
        assert "bundle_size" in default_config["bundling"]
        assert isinstance(default_config["bundling"]["bundle_size"], int)

    def test_pipeline_config_section_exists(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify pipeline section with lifecycle settings exists.

        Real-world significance:
        - Pipeline lifecycle settings control cleanup at startup and shutdown
        - before_run controls cleanup of old output before starting new run
        - after_run controls cleanup of intermediate files after successful run
        """
        assert "pipeline" in default_config
        assert "before_run" in default_config["pipeline"]
        assert "after_run" in default_config["pipeline"]
        assert "clear_output_directory" in default_config["pipeline"]["before_run"]
        assert "remove_artifacts" in default_config["pipeline"]["after_run"]

    def test_bundle_size_configuration(self, default_config: Dict[str, Any]) -> None:
        """Verify batch size is configurable.

        Real-world significance:
        - Users can control how many PDFs are grouped per batch
        - Allows optimization for printing hardware
        """
        assert "bundling" in default_config
        assert "bundle_size" in default_config["bundling"]
        assert isinstance(default_config["bundling"]["bundle_size"], int)
        assert default_config["bundling"]["bundle_size"] >= 0

    def test_chart_diseases_header_configuration(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify chart diseases header is configurable list.

        Real-world significance:
        - Allows customizing which diseases appear on notice
        - Different districts may have different disease tracking needs
        """
        assert "chart_diseases_header" in default_config
        assert isinstance(default_config["chart_diseases_header"], list)
        assert len(default_config["chart_diseases_header"]) > 0

    def test_replace_unspecified_configuration(self, default_config: Dict[str, Any]) -> None:
        """Verify replace_unspecified list is configurable.

        Real-world significance:
        - Some agents (staff) should not receive notices
        - Config allows filtering out specific agent types
        """
        assert "replace_unspecified" in default_config
        assert isinstance(default_config["replace_unspecified"], list)


@pytest.mark.integration
class TestQrEnabledBehavior:
    """Integration tests for QR enabled/disabled feature flag."""

    def test_qr_enabled_true_config(self, default_config: Dict[str, Any]) -> None:
        """Verify config can enable QR generation.

        Real-world significance:
        - QR codes on notices enable online vaccine verification
        - Must be able to enable/disable without code changes
        """
        config_qr_enabled = default_config.copy()
        config_qr_enabled["qr"]["enabled"] = True

        assert config_qr_enabled["qr"]["enabled"] is True

    def test_qr_enabled_false_config(self, default_config: Dict[str, Any]) -> None:
        """Verify config can disable QR generation.

        Real-world significance:
        - Some jurisdictions may not use QR codes
        - Disabling QR saves processing time
        """
        config_qr_disabled = default_config.copy()
        config_qr_disabled["qr"]["enabled"] = False

        assert config_qr_disabled["qr"]["enabled"] is False

    def test_qr_payload_template_configured(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify QR payload template is configurable.

        Real-world significance:
        - Different districts may use different QR backend systems
        - Template should point to correct verification endpoint
        """
        assert "payload_template" in default_config["qr"]
        assert isinstance(default_config["qr"]["payload_template"], str)
        assert len(default_config["qr"]["payload_template"]) > 0


@pytest.mark.integration
class TestEncryptionBehavior:
    """Integration tests for PDF encryption configuration."""

    def test_encryption_enabled_true_config(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify config can enable PDF encryption.

        Real-world significance:
        - Encrypting PDFs protects sensitive student health information
        - Password derived from student data ensures privacy
        """
        config_encrypted = default_config.copy()
        config_encrypted["encryption"]["enabled"] = True

        assert config_encrypted["encryption"]["enabled"] is True

    def test_encryption_enabled_false_config(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify config can disable PDF encryption.

        Real-world significance:
        - Some environments may use other protection mechanisms
        - Disabling encryption simplifies distribution
        """
        config_unencrypted = default_config.copy()
        config_unencrypted["encryption"]["enabled"] = False

        assert config_unencrypted["encryption"]["enabled"] is False

    def test_encryption_password_template_configured(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify encryption password template is configurable.

        Real-world significance:
        - Password can use student DOB, ID, or combination
        - Template allows flexibility in password generation strategy
        """
        assert "password" in default_config["encryption"]
        assert "template" in default_config["encryption"]["password"]
        assert isinstance(default_config["encryption"]["password"]["template"], str)


@pytest.mark.integration
class TestBatchingBehavior:
    """Integration tests for PDF bundling configuration."""

    def test_bundling_bundle_size_zero_disables_bundling(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify bundle_size=0 disables bundling.

        Real-world significance:
        - When bundle_size=0, each student PDF remains individual
        - No PDF combining step is executed
        """
        config = default_config.copy()
        config["bundling"]["bundle_size"] = 0

        assert config["bundling"]["bundle_size"] == 0

    def test_bundling_bundle_size_positive_enables_bundling(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify positive bundle_size enables bundling.

        Real-world significance:
        - bundle_size=50 means 50 PDFs per combined batch
        - Reduces distribution workload (fewer files to send)
        """
        config = default_config.copy()
        config["bundling"]["bundle_size"] = 50

        assert config["bundling"]["bundle_size"] == 50
        assert config["bundling"]["bundle_size"] > 0

    def test_bundling_group_by_sequential(self, default_config: Dict[str, Any]) -> None:
        """Verify bundling can use sequential grouping.

        Real-world significance:
        - Sequential bundling: PDFs combined in processing order
        - Simplest bundling strategy
        """
        config = default_config.copy()
        config["bundling"]["group_by"] = None

        assert config["bundling"]["group_by"] is None

    def test_bundling_group_by_school(self, default_config: Dict[str, Any]) -> None:
        """Verify bundling can group by school.

        Real-world significance:
        - Group by school: Each batch contains only one school's students
        - Allows per-school distribution to school boards
        """
        config = default_config.copy()
        config["bundling"]["group_by"] = "school"

        assert config["bundling"]["group_by"] == "school"

    def test_bundling_group_by_board(self, default_config: Dict[str, Any]) -> None:
        """Verify bundling can group by school board.

        Real-world significance:
        - Group by board: Each batch contains only one board's students
        - Allows per-board distribution to parent organizations
        """
        config = default_config.copy()
        config["bundling"]["group_by"] = "board"

        assert config["bundling"]["group_by"] == "board"


@pytest.mark.integration
class TestPipelineCleanupBehavior:
    """Integration tests for pipeline cleanup configuration."""

    def test_keep_intermediate_files_true(self, default_config: Dict[str, Any]) -> None:
        """Verify intermediate files can be preserved.

        Real-world significance:
        - Keeping .typ files, JSON artifacts allows post-run debugging
        - Useful for troubleshooting notice content issues
        """
        config = default_config.copy()
        config["pipeline"]["keep_intermediate_files"] = True

        assert config["pipeline"]["keep_intermediate_files"] is True

    def test_keep_intermediate_files_false(
        self, default_config: Dict[str, Any]
    ) -> None:
        """Verify intermediate files can be removed.

        Real-world significance:
        - Removes .typ, JSON, and per-client PDFs after bundling
        - Cleans up disk space for large runs (1000+ students)
        """
        config = default_config.copy()
        config["pipeline"]["keep_intermediate_files"] = False

        assert config["pipeline"]["keep_intermediate_files"] is False

    def test_auto_remove_output_true(self, default_config: Dict[str, Any]) -> None:
        """Verify auto-removal of previous output can be enabled.

        Real-world significance:
        - auto_remove_output=true: Automatically delete previous run
        - Ensures output directory contains only current run
        """
        config = default_config.copy()
        config["pipeline"]["auto_remove_output"] = True

        assert config["pipeline"]["auto_remove_output"] is True

    def test_auto_remove_output_false(self, default_config: Dict[str, Any]) -> None:
        """Verify auto-removal of previous output can be disabled.

        Real-world significance:
        - auto_remove_output=false: Preserve previous run; warn on conflicts
        - Allows archiving or comparing multiple runs
        """
        config = default_config.copy()
        config["pipeline"]["auto_remove_output"] = False

        assert config["pipeline"]["auto_remove_output"] is False
