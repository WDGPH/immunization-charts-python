"""Unit tests for cleanup module - Intermediate file removal.

Tests cover:
- Safe file and directory deletion
- Selective cleanup (preserve PDFs, remove .typ files)
- Configuration-driven cleanup behavior
- Error handling for permission issues and missing paths
- File extension filtering
- Nested directory removal

Real-world significance:
- Step 9 of pipeline (optional): removes intermediate artifacts (.typ files, etc.)
- Keeps output directory clean and storage minimal
- Must preserve final PDFs while removing working files
- Configuration controls what gets deleted (cleanup.remove_directories)
- Runs only if pipeline.keep_intermediate_files: false
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import cleanup


@pytest.mark.unit
class TestSafeDelete:
    """Unit tests for safe_delete function."""

    def test_safe_delete_removes_file(self, tmp_test_dir: Path) -> None:
        """Verify file is deleted safely.

        Real-world significance:
        - Must delete intermediate .typ files
        - Should not crash if file already missing
        """
        test_file = tmp_test_dir / "test.typ"
        test_file.write_text("content")

        cleanup.safe_delete(test_file)

        assert not test_file.exists()

    def test_safe_delete_removes_directory(self, tmp_test_dir: Path) -> None:
        """Verify directory and contents are deleted recursively.

        Real-world significance:
        - Should delete entire artifact directory structures
        - Cleans up nested directories (e.g., artifacts/qr_codes/)
        """
        test_dir = tmp_test_dir / "artifacts"
        test_dir.mkdir()
        (test_dir / "file1.json").write_text("data")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "file2.json").write_text("data")

        cleanup.safe_delete(test_dir)

        assert not test_dir.exists()

    def test_safe_delete_missing_file_doesnt_error(self, tmp_test_dir: Path) -> None:
        """Verify no error when file already missing.

        Real-world significance:
        - Cleanup might run multiple times on same directory
        - Should be idempotent (safe to call multiple times)
        """
        missing_file = tmp_test_dir / "nonexistent.typ"

        # Should not raise
        cleanup.safe_delete(missing_file)

        assert not missing_file.exists()

    def test_safe_delete_missing_directory_doesnt_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify no error when directory already missing.

        Real-world significance:
        - Directory may have been deleted already
        - Cleanup should be idempotent
        """
        missing_dir = tmp_test_dir / "artifacts"

        # Should not raise
        cleanup.safe_delete(missing_dir)

        assert not missing_dir.exists()


@pytest.mark.unit
@pytest.mark.unit
class TestCleanupWithConfig:
    """Unit tests for cleanup_with_config function."""

    def test_cleanup_removes_configured_directories(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify configured directories are removed.

        Real-world significance:
        - Config specifies which directories to remove (cleanup.remove_directories)
        - Common setup: remove artifacts/ and pdf_individual/
        - Preserves pdf_combined/ with final batched PDFs
        """
        output_dir = tmp_output_structure["root"]

        # Create test structure
        (tmp_output_structure["artifacts"] / "typst").mkdir()
        (tmp_output_structure["artifacts"] / "typst" / "notice_00001.typ").write_text(
            "typ"
        )
        (tmp_output_structure["metadata"] / "page_counts.json").write_text("data")

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories:\n    - artifacts\n    - metadata\n"
        )

        cleanup.cleanup_with_config(output_dir, config_path)

        assert not tmp_output_structure["artifacts"].exists()
        assert not tmp_output_structure["metadata"].exists()
        assert tmp_output_structure["pdf_individual"].exists()

    def test_cleanup_with_missing_config_uses_defaults(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify cleanup works with missing config (uses defaults).

        Real-world significance:
        - Config might use defaults if cleanup section missing
        - Pipeline should still complete
        """
        output_dir = tmp_output_structure["root"]

        # Config without cleanup section
        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\npipeline:\n  keep_intermediate_files: false\n"
        )

        # Should not raise
        cleanup.cleanup_with_config(output_dir, config_path)

    def test_cleanup_with_empty_remove_list(self, tmp_output_structure: dict) -> None:
        """Verify empty remove_directories list doesn't delete anything.

        Real-world significance:
        - Config might disable cleanup by providing empty list
        - Useful for testing or keeping all artifacts
        """
        output_dir = tmp_output_structure["root"]

        (tmp_output_structure["artifacts"] / "test.json").write_text("data")

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories: []\n"
        )

        cleanup.cleanup_with_config(output_dir, config_path)

        assert (tmp_output_structure["artifacts"] / "test.json").exists()

    def test_cleanup_with_nonexistent_directory_in_config(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify cleanup doesn't error on nonexistent directories.

        Real-world significance:
        - Config might list directories that don't exist
        - Should handle gracefully (idempotent)
        """
        output_dir = tmp_output_structure["root"]

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories:\n    - nonexistent_dir\n    - artifacts\n"
        )

        # Should not raise
        cleanup.cleanup_with_config(output_dir, config_path)


@pytest.mark.unit
class TestMain:
    """Unit tests for main cleanup entry point."""

    def test_main_validates_output_directory(self, tmp_test_dir: Path) -> None:
        """Verify error if output_dir is not a directory.

        Real-world significance:
        - Caller should pass a directory, not a file
        - Should validate input before attempting cleanup
        """
        invalid_path = tmp_test_dir / "file.txt"
        invalid_path.write_text("not a directory")

        with pytest.raises(ValueError, match="not a valid directory"):
            cleanup.main(invalid_path)

    def test_main_calls_cleanup_with_config(self, tmp_output_structure: dict) -> None:
        """Verify main entry point calls cleanup_with_config.

        Real-world significance:
        - Main is entry point from run_pipeline.py
        - Should load and apply cleanup configuration
        """
        output_dir = tmp_output_structure["root"]

        (tmp_output_structure["artifacts"] / "test.json").write_text("data")

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories:\n    - artifacts\n"
        )

        cleanup.main(output_dir, config_path)

        assert not tmp_output_structure["artifacts"].exists()

    def test_main_with_none_config_path_uses_default(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify main works with config_path=None (uses default location).

        Real-world significance:
        - run_pipeline.py might not pass config_path
        - Should use default location (config/parameters.yaml)
        """
        output_dir = tmp_output_structure["root"]

        # Should not raise (will use defaults)
        cleanup.main(output_dir, config_path=None)


@pytest.mark.unit
class TestCleanupIntegration:
    """Unit tests for cleanup workflow integration."""

    def test_cleanup_preserves_pdfs_removes_typ(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify complete cleanup workflow: remove .typ, keep PDFs.

        Real-world significance:
        - Most common cleanup scenario:
          - Remove .typ templates (intermediate)
          - Keep .pdf files (final output)
        - Reduces storage footprint significantly
        """
        output_dir = tmp_output_structure["root"]

        # Create test files
        (tmp_output_structure["artifacts"] / "notice_00001.typ").write_text("template")
        (tmp_output_structure["pdf_individual"] / "notice_00001.pdf").write_text(
            "pdf content"
        )

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories:\n    - artifacts\n"
        )

        cleanup.cleanup_with_config(output_dir, config_path)

        assert not (tmp_output_structure["artifacts"] / "notice_00001.typ").exists()
        assert (tmp_output_structure["pdf_individual"] / "notice_00001.pdf").exists()

    def test_cleanup_multiple_calls_idempotent(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify cleanup can be called multiple times safely.

        Real-world significance:
        - If cleanup runs twice, should not error
        - Idempotent operation: no side effects from repeated runs
        """
        output_dir = tmp_output_structure["root"]

        config_path = output_dir / "parameters.yaml"
        config_path.write_text(
            "qr:\n  enabled: false\ncleanup:\n  remove_directories:\n    - artifacts\n"
        )

        # First call
        cleanup.cleanup_with_config(output_dir, config_path)

        # Second call should not raise
        cleanup.cleanup_with_config(output_dir, config_path)

        assert not tmp_output_structure["artifacts"].exists()
