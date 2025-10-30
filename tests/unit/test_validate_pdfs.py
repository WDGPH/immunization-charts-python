"""Unit tests for validate_pdfs module.

Tests PDF validation functionality including:
- PDF file discovery from directory or file path
- Language-based filtering for multi-language output
- PDF structure validation (page count, layout markers)
- Validation summary generation and aggregation
- JSON metadata output for validation results
- Error handling with configurable rule severity levels

Tests use temporary directories (tmp_path) for file I/O and mock pypdf to
create test PDFs without external dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from pipeline import validate_pdfs


@pytest.mark.unit
class TestDiscoverPdfs:
    """Tests for PDF discovery functionality."""

    def test_discover_pdfs_in_directory(self, tmp_path: Path) -> None:
        """Verify PDF discovery finds all PDFs in a directory.

        Real-world significance:
        - Pipeline validates all compiled PDFs from a batch
        - Discovery must be deterministic and comprehensive
        - Enables consistent validation across different run sizes

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If discovered PDF count doesn't match created count

        Assertion: All PDFs in directory are discovered and have .pdf suffix
        """
        # Create test PDF files
        for i in range(3):
            pdf_path = tmp_path / f"test_{i}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)

        pdfs = validate_pdfs.discover_pdfs(tmp_path)
        assert len(pdfs) == 3
        assert all(p.suffix == ".pdf" for p in pdfs)

    def test_discover_pdfs_single_file(self, tmp_path: Path) -> None:
        """Verify PDF discovery accepts both directories and single files.

        Real-world significance:
        - Validation may run on entire batch or individual PDF for debugging
        - Single-file mode enables manual PDF validation without batch context
        - Flexible input enables different usage patterns

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If single file path not recognized as valid PDF input

        Assertion: Single PDF file is discovered and returned in list
        """
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        pdfs = validate_pdfs.discover_pdfs(pdf_path)
        assert len(pdfs) == 1
        assert pdfs[0] == pdf_path

    def test_discover_pdfs_no_files_empty_dir(self, tmp_path: Path) -> None:
        """Verify PDF discovery handles empty directories gracefully.

        Real-world significance:
        - Optional pipeline steps may not create PDFs
        - Validation must not crash on missing output
        - Enables idempotent pipeline execution

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If empty directory doesn't return empty list

        Assertion: Empty directory returns empty PDF list
        """
        pdfs = validate_pdfs.discover_pdfs(tmp_path)
        assert len(pdfs) == 0

    def test_discover_pdfs_invalid_path(self, tmp_path: Path) -> None:
        """Verify PDF discovery fails fast on invalid paths.

        Real-world significance:
        - Configuration errors (wrong directory) should be caught immediately
        - Prevents silent skipping of validation or misleading success messages
        - Enables clear error messages for operators to debug

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        FileNotFoundError
            If path does not exist (expected behavior)

        AssertionError
            If invalid path does not raise FileNotFoundError

        Assertion: Invalid path raises FileNotFoundError
        """
        invalid_path = tmp_path / "nonexistent.pdf"
        with pytest.raises(FileNotFoundError):
            validate_pdfs.discover_pdfs(invalid_path)


@pytest.mark.unit
class TestFilterByLanguage:
    """Tests for language filtering."""

    def test_filter_by_language_en(self, tmp_path: Path) -> None:
        """Verify language filtering correctly separates multi-language output.

        Real-world significance:
        - Pipeline generates notices in both English and French
        - Validation must run separately per language to report accurate statistics
        - Enables language-specific quality control (e.g., signature placement varies)

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If language filter doesn't correctly select files or includes other languages

        Assertion: Only English-prefixed PDFs are selected from mixed language set
        """
        files = [
            tmp_path / "en_notice_001.pdf",
            tmp_path / "fr_notice_001.pdf",
            tmp_path / "en_notice_002.pdf",
        ]
        filtered = validate_pdfs.filter_by_language(files, "en")
        assert len(filtered) == 2
        assert all("en_" in f.name for f in filtered)

    def test_filter_by_language_none(self, tmp_path: Path) -> None:
        """Verify no language filter returns all PDFs unchanged.

        Real-world significance:
        - Pipeline may validate entire batch without language separation
        - Enables single validation run for mixed language output
        - Ensures filtering doesn't accidentally exclude files

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If language filter unexpectedly modifies file list when None

        Assertion: All PDFs returned when language filter is None
        """
        files = [
            tmp_path / "en_notice_001.pdf",
            tmp_path / "fr_notice_001.pdf",
        ]
        filtered = validate_pdfs.filter_by_language(files, None)
        assert len(filtered) == 2


@pytest.mark.unit
class TestValidatePdfStructure:
    """Tests for PDF structure validation."""

    def test_validate_pdf_structure_basic(self, tmp_path: Path) -> None:
        """Verify PDF with correct structure (2 pages) passes validation.

        Real-world significance:
        - Standard immunization notices are 2 pages (notice + immunization record)
        - Validation must correctly identify well-formed PDFs
        - Establishes baseline for warning detection (valid ≠ warned)

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If valid PDF is incorrectly marked as failed

        Assertion: PDF with exactly 2 pages and no layout issues passes validation
        """
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        result = validate_pdfs.validate_pdf_structure(pdf_path, enabled_rules={})
        assert result.filename == "test.pdf"
        assert result.page_count == 2
        assert result.passed
        assert len(result.warnings) == 0

    def test_validate_pdf_structure_unexpected_pages(self, tmp_path: Path) -> None:
        """Verify validation detects and warns on incorrect page count.

        Real-world significance:
        - PDF compilation errors may produce wrong page counts
        - Warnings enable operators to detect template/Typst issues
        - QA step must catch layout problems before delivery

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If page count warning not generated for non-2-page PDF

        Assertion: PDF with 3 pages generates exactly_two_pages warning
        """
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        result = validate_pdfs.validate_pdf_structure(
            pdf_path,
            enabled_rules={"exactly_two_pages": "warn"},
        )
        assert result.page_count == 3
        assert not result.passed
        assert len(result.warnings) == 1
        assert "exactly_two_pages" in result.warnings[0]

    def test_validate_pdf_structure_rule_disabled(self, tmp_path: Path) -> None:
        """Verify disabled rules do not generate warnings (configurable validation).

        Real-world significance:
        - Operators may disable specific rules for testing or edge cases
        - Configuration-driven behavior enables workflow flexibility
        - Disabled rules prevent false positives when rules don't apply

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If disabled rule still generates warnings

        Assertion: PDF with 3 pages passes when exactly_two_pages rule is disabled
        """
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        result = validate_pdfs.validate_pdf_structure(
            pdf_path,
            enabled_rules={"exactly_two_pages": "disabled"},
        )
        assert result.page_count == 3
        assert result.passed  # No warning because rule is disabled
        assert not result.warnings


@pytest.mark.unit
class TestValidationSummary:
    """Tests for validation summary generation."""

    def test_validate_pdfs_summary(self, tmp_path: Path) -> None:
        """Verify batch validation generates accurate summary statistics.

        Real-world significance:
        - Operators need aggregate statistics to understand batch quality
        - Summary enables trend analysis across multiple runs
        - Pass/fail counts inform decision on whether to proceed

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If summary statistics don't match input PDFs

        Assertion: Summary correctly reports passed, warned, and page distributions
        """
        # Create test PDFs with different page counts
        files = []
        for i in range(3):
            pdf_path = tmp_path / f"test_{i}.pdf"
            writer = PdfWriter()
            for _ in range(2 if i < 2 else 3):
                writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)
            files.append(pdf_path)

        summary = validate_pdfs.validate_pdfs(
            files,
            enabled_rules={"exactly_two_pages": "warn"},
        )
        assert summary.total_pdfs == 3
        assert summary.passed_count == 2
        assert summary.warning_count == 1
        assert summary.page_count_distribution[2] == 2
        assert summary.page_count_distribution[3] == 1


@pytest.mark.unit
class TestWriteValidationJson:
    """Tests for JSON output."""

    def test_write_validation_json(self, tmp_path: Path) -> None:
        """Verify validation summary exports to JSON for downstream processing.

        Real-world significance:
        - JSON metadata enables integration with external analysis tools
        - Persistent records support audit trail and debugging
        - Enables programmatic post-processing of validation results

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If JSON output missing expected keys or values

        Assertion: JSON output contains all summary statistics and per-PDF results
        """
        summary = validate_pdfs.ValidationSummary(
            language="en",
            total_pdfs=2,
            passed_count=1,
            warning_count=1,
            page_count_distribution={2: 1, 3: 1},
            warning_types={"exactly_two_pages": 1},
            results=[
                validate_pdfs.ValidationResult(
                    filename="test1.pdf", page_count=2, warnings=[], passed=True
                ),
                validate_pdfs.ValidationResult(
                    filename="test2.pdf",
                    page_count=3,
                    warnings=["exactly_two_pages: 3 pages (expected 2)"],
                    passed=False,
                ),
            ],
        )

        output_path = tmp_path / "validation.json"
        validate_pdfs.write_validation_json(summary, output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["total_pdfs"] == 2
        assert data["passed_count"] == 1
        assert data["warning_count"] == 1
        assert len(data["results"]) == 2


@pytest.mark.unit
class TestMainFunction:
    """Tests for main entry point."""

    def test_main_with_json_output(self, tmp_path: Path) -> None:
        """Verify main entry point orchestrates validation and produces JSON output.

        Real-world significance:
        - Pipeline orchestrator calls main() as step 6
        - Validates all compiled PDFs and reports aggregate results
        - Enables downstream decisions on whether to proceed (e.g., email delivery)

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        AssertionError
            If JSON output not created or summary statistics incorrect

        Assertion: Valid PDFs pass, JSON metadata is written, summary is returned
        """
        # Create test PDFs
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()
        for i in range(2):
            pdf_path = pdf_dir / f"en_notice_{i:03d}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)

        json_path = tmp_path / "validation.json"
        summary = validate_pdfs.main(
            pdf_dir,
            language="en",
            enabled_rules={"exactly_two_pages": "warn"},
            json_output=json_path,
        )

        assert summary.total_pdfs == 2
        assert summary.passed_count == 2
        assert json_path.exists()

    def test_main_with_error_rule(self, tmp_path: Path) -> None:
        """Verify main halts pipeline when error-level validation rule fails.

        Real-world significance:
        - Some validation issues are critical and must prevent delivery
        - Error-level rules enable strict quality gates
        - Prevents defective notices from reaching clients

        Parameters
        ----------
        tmp_path : Path
            Pytest fixture providing temporary directory

        Raises
        ------
        RuntimeError
            When validation rule with severity 'error' detects failure (expected)

        AssertionError
            If main does not raise RuntimeError for error-level validation failure

        Assertion: main() raises RuntimeError when error-level rule detects issue
        """
        # Create test PDFs with wrong page count
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()
        pdf_path = pdf_dir / "test.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        with pytest.raises(RuntimeError, match="PDF validation failed with errors"):
            validate_pdfs.main(
                pdf_dir,
                enabled_rules={"exactly_two_pages": "error"},
                json_output=None,
            )
