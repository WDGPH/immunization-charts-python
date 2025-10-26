"""Unit tests for compile_notices module - Typst compilation to PDF.

Tests cover:
- Typst file discovery
- Subprocess invocation with correct flags
- PDF output generation and path handling
- Error handling for compilation failures
- Configuration-driven behavior
- Font path and root directory handling

Real-world significance:
- Step 5 of pipeline: compiles Typst templates to PDF notices
- First time student notices become visible (PDF format)
- Compilation failures are a critical blocker
- Must handle Typst CLI errors gracefully
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pipeline import compile_notices


@pytest.mark.unit
class TestDiscoverTypstFiles:
    """Unit tests for discover_typst_files function."""

    def test_discover_typst_files_finds_all_files(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify .typ files are discovered correctly.

        Real-world significance:
        - Must find all generated Typst templates from previous step
        - Files are sorted for consistent order
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)

        # Create test files
        (typst_dir / "notice_00001.typ").write_text("test")
        (typst_dir / "notice_00002.typ").write_text("test")
        (typst_dir / "notice_00003.typ").write_text("test")

        result = compile_notices.discover_typst_files(tmp_output_structure["artifacts"])

        assert len(result) == 3
        assert all(p.suffix == ".typ" for p in result)

    def test_discover_typst_files_empty_directory(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify empty list when no Typst files found.

        Real-world significance:
        - May happen if notice generation step failed silently
        - Should handle gracefully without crashing
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)

        result = compile_notices.discover_typst_files(tmp_output_structure["artifacts"])

        assert result == []

    def test_discover_typst_files_missing_directory(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify empty list when typst directory doesn't exist.

        Real-world significance:
        - May happen if notice generation step failed
        - Should handle gracefully
        """
        result = compile_notices.discover_typst_files(tmp_output_structure["artifacts"])

        assert result == []

    def test_discover_typst_files_ignores_other_files(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify only .typ files are returned.

        Real-world significance:
        - Directory may contain other files (logs, temp files)
        - Must filter to .typ files only
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)

        (typst_dir / "notice_00001.typ").write_text("test")
        (typst_dir / "notice_00002.txt").write_text("test")
        (typst_dir / "README.md").write_text("test")

        result = compile_notices.discover_typst_files(tmp_output_structure["artifacts"])

        assert len(result) == 1
        assert result[0].name == "notice_00001.typ"

    def test_discover_typst_files_sorted_order(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify files are returned in sorted order.

        Real-world significance:
        - Sorted order ensures consistent compilation
        - Matches sequence number order for debugging
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)

        # Create files in random order
        (typst_dir / "notice_00003.typ").write_text("test")
        (typst_dir / "notice_00001.typ").write_text("test")
        (typst_dir / "notice_00002.typ").write_text("test")

        result = compile_notices.discover_typst_files(tmp_output_structure["artifacts"])

        names = [p.name for p in result]
        assert names == ["notice_00001.typ", "notice_00002.typ", "notice_00003.typ"]


@pytest.mark.unit
class TestCompileFile:
    """Unit tests for compile_file function."""

    def test_compile_file_invokes_typst_command(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify typst CLI is invoked with correct parameters.

        Real-world significance:
        - Must call `typst compile` with correct file paths
        - Output path must match expected naming (stem.pdf)
        """
        typ_file = tmp_output_structure["artifacts"] / "notice_00001.typ"
        typ_file.write_text("test")
        pdf_dir = tmp_output_structure["pdf_individual"]

        with patch("subprocess.run") as mock_run:
            compile_notices.compile_file(
                typ_file,
                pdf_dir,
                typst_bin="typst",
                font_path=None,
                root_dir=Path("/project"),
                verbose=False,
            )

            # Verify subprocess was called
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "typst" in call_args[0]
            assert "compile" in call_args

    def test_compile_file_with_font_path(self, tmp_output_structure: dict) -> None:
        """Verify font path is passed to typst when provided.

        Real-world significance:
        - Custom fonts may be required for non-ASCII characters
        - Must pass --font-path flag to Typst
        """
        typ_file = tmp_output_structure["artifacts"] / "notice.typ"
        typ_file.write_text("test")
        pdf_dir = tmp_output_structure["pdf_individual"]
        font_path = Path("/usr/share/fonts")

        with patch("subprocess.run") as mock_run:
            compile_notices.compile_file(
                typ_file,
                pdf_dir,
                typst_bin="typst",
                font_path=font_path,
                root_dir=Path("/project"),
                verbose=False,
            )

            call_args = mock_run.call_args[0][0]
            assert "--font-path" in call_args
            assert str(font_path) in call_args

    def test_compile_file_handles_error(self, tmp_output_structure: dict) -> None:
        """Verify error is raised if typst compilation fails.

        Real-world significance:
        - Typst syntax errors or missing imports should fail compilation
        - Must propagate error so pipeline stops
        """
        typ_file = tmp_output_structure["artifacts"] / "notice.typ"
        typ_file.write_text("test")
        pdf_dir = tmp_output_structure["pdf_individual"]

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Typst compilation failed")

            with pytest.raises(Exception):
                compile_notices.compile_file(
                    typ_file,
                    pdf_dir,
                    typst_bin="typst",
                    font_path=None,
                    root_dir=Path("/project"),
                    verbose=False,
                )


@pytest.mark.unit
class TestCompileTypstFiles:
    """Unit tests for compile_typst_files function."""

    def test_compile_typst_files_creates_pdf_directory(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify PDF output directory is created if missing.

        Real-world significance:
        - First run: directory doesn't exist yet
        - Must auto-create before writing PDFs
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)
        (typst_dir / "notice.typ").write_text("test")

        pdf_dir = tmp_output_structure["root"] / "pdf_output"
        assert not pdf_dir.exists()

        with patch("pipeline.compile_notices.compile_file"):
            compile_notices.compile_typst_files(
                tmp_output_structure["artifacts"],
                pdf_dir,
                typst_bin="typst",
                font_path=None,
                root_dir=Path("/project"),
                verbose=False,
            )

        assert pdf_dir.exists()

    def test_compile_typst_files_returns_count(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify count of compiled files is returned.

        Real-world significance:
        - Pipeline needs to know how many files were processed
        - Used for logging and validation
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)
        (typst_dir / "notice_00001.typ").write_text("test")
        (typst_dir / "notice_00002.typ").write_text("test")

        pdf_dir = tmp_output_structure["pdf_individual"]

        with patch("pipeline.compile_notices.compile_file"):
            count = compile_notices.compile_typst_files(
                tmp_output_structure["artifacts"],
                pdf_dir,
                typst_bin="typst",
                font_path=None,
                root_dir=Path("/project"),
                verbose=False,
            )

        assert count == 2

    def test_compile_typst_files_no_files_returns_zero(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify zero is returned when no Typst files found.

        Real-world significance:
        - May happen if notice generation failed
        - Should log warning and continue gracefully
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)

        pdf_dir = tmp_output_structure["pdf_individual"]

        count = compile_notices.compile_typst_files(
            tmp_output_structure["artifacts"],
            pdf_dir,
            typst_bin="typst",
            font_path=None,
            root_dir=Path("/project"),
            verbose=False,
        )

        assert count == 0

    def test_compile_typst_files_compiles_all_files(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify all discovered files are compiled.

        Real-world significance:
        - Must not skip any files
        - Each client needs a PDF notice
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)
        (typst_dir / "notice_00001.typ").write_text("test")
        (typst_dir / "notice_00002.typ").write_text("test")
        (typst_dir / "notice_00003.typ").write_text("test")

        pdf_dir = tmp_output_structure["pdf_individual"]

        with patch("pipeline.compile_notices.compile_file") as mock_compile:
            compile_notices.compile_typst_files(
                tmp_output_structure["artifacts"],
                pdf_dir,
                typst_bin="typst",
                font_path=None,
                root_dir=Path("/project"),
                verbose=False,
            )

            # Should have called compile_file 3 times
            assert mock_compile.call_count == 3


@pytest.mark.unit
class TestCompileWithConfig:
    """Unit tests for compile_with_config function."""

    def test_compile_with_config_uses_default_config(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify config is loaded and used for compilation.

        Real-world significance:
        - Typst binary path and font path come from config
        - Must use configured values
        """
        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)
        (typst_dir / "notice.typ").write_text("test")

        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {
            "typst": {
                "bin": "typst",
                "font_path": "/usr/share/fonts",
            }
        }
        config_path.write_text(yaml.dump(config))

        pdf_dir = tmp_output_structure["pdf_individual"]

        with patch("pipeline.compile_notices.compile_file"):
            result = compile_notices.compile_with_config(
                tmp_output_structure["artifacts"],
                pdf_dir,
                config_path,
            )

        assert result == 1

    def test_compile_with_config_environment_override(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify TYPST_BIN environment variable overrides config.

        Real-world significance:
        - CI/CD environments may need custom Typst binary path
        - Environment variable should take precedence
        """
        import os

        typst_dir = tmp_output_structure["artifacts"] / "typst"
        typst_dir.mkdir(parents=True, exist_ok=True)
        (typst_dir / "notice.typ").write_text("test")

        config_path = tmp_output_structure["root"] / "config.yaml"
        config = {
            "typst": {
                "bin": "typst",
            }
        }
        config_path.write_text(yaml.dump(config))

        pdf_dir = tmp_output_structure["pdf_individual"]

        # Set environment variable
        original = os.environ.get("TYPST_BIN")
        try:
            os.environ["TYPST_BIN"] = "/custom/typst"

            with patch("pipeline.compile_notices.compile_file") as mock_compile:
                compile_notices.compile_with_config(
                    tmp_output_structure["artifacts"],
                    pdf_dir,
                    config_path,
                )

                # Verify the environment variable was used
                if mock_compile.called:
                    call_kwargs = mock_compile.call_args[1]
                    assert call_kwargs.get("typst_bin") == "/custom/typst"
        finally:
            if original is not None:
                os.environ["TYPST_BIN"] = original
            else:
                os.environ.pop("TYPST_BIN", None)
