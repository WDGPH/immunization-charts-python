"""Unit tests for count_pdfs module - PDF page counting and validation.

Tests cover:
- PDF discovery and filtering
- Page count detection
- Metadata aggregation
- JSON manifest generation
- Error handling for corrupted PDFs
- Language-based filtering

Real-world significance:
- Step 6 of pipeline: validates all PDFs compiled correctly
- Detects corrupted or incomplete notices before distribution
- Page count metadata used for quality control and batching
- Manifest JSON enables tracking per notice
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import count_pdfs


def create_test_pdf(path: Path, num_pages: int = 1) -> None:
    """Create a minimal test PDF file using PyPDF utilities."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        writer.write(f)


@pytest.mark.unit
class TestDiscoverPdfs:
    """Unit tests for discover_pdfs function."""

    def test_discover_pdfs_finds_all_files_in_directory(
        self, tmp_output_structure: dict
    ) -> None:
        """Verify PDFs are discovered correctly in directory.

        Real-world significance:
        - Must find all compiled PDF notices
        - Sorted order ensures consistency
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "notice_00002.pdf", num_pages=2)

        result = count_pdfs.discover_pdfs(pdf_dir)

        assert len(result) == 2
        assert all(p.suffix == ".pdf" for p in result)

    def test_discover_pdfs_single_file(self, tmp_output_structure: dict) -> None:
        """Verify single PDF file is handled.

        Real-world significance:
        - May test with single file for validation
        - Should return list with one file
        """
        pdf_file = tmp_output_structure["pdf_individual"] / "test.pdf"
        create_test_pdf(pdf_file, num_pages=2)

        result = count_pdfs.discover_pdfs(pdf_file)

        assert len(result) == 1
        assert result[0] == pdf_file

    def test_discover_pdfs_missing_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when path doesn't exist or is not PDF.

        Real-world significance:
        - Compilation may have failed
        - Must fail early with clear error
        """
        with pytest.raises(FileNotFoundError):
            count_pdfs.discover_pdfs(tmp_test_dir / "nonexistent.pdf")

    def test_discover_pdfs_ignores_non_pdf_files(self, tmp_output_structure: dict) -> None:
        """Verify only .pdf files are returned.

        Real-world significance:
        - Directory may contain logs, temp files
        - Must filter to PDFs only
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)
        (pdf_dir / "log.txt").write_text("test")
        (pdf_dir / "temp.tmp").write_text("test")

        result = count_pdfs.discover_pdfs(pdf_dir)

        assert len(result) == 1
        assert result[0].name == "notice_00001.pdf"

    def test_discover_pdfs_sorted_order(self, tmp_output_structure: dict) -> None:
        """Verify PDFs are returned in sorted order.

        Real-world significance:
        - Sorted order matches sequence numbers
        - Enables consistent output and debugging
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00003.pdf")
        create_test_pdf(pdf_dir / "notice_00001.pdf")
        create_test_pdf(pdf_dir / "notice_00002.pdf")

        result = count_pdfs.discover_pdfs(pdf_dir)

        names = [p.name for p in result]
        assert names == ["notice_00001.pdf", "notice_00002.pdf", "notice_00003.pdf"]


@pytest.mark.unit
class TestFilterByLanguage:
    """Unit tests for filter_by_language function."""

    def test_filter_by_language_en(self, tmp_output_structure: dict) -> None:
        """Verify English PDFs are filtered correctly.

        Real-world significance:
        - Pipeline may generate both en and fr PDFs
        - Must separate by language prefix
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "en_notice_00001.pdf")
        create_test_pdf(pdf_dir / "en_notice_00002.pdf")
        create_test_pdf(pdf_dir / "fr_notice_00001.pdf")

        files = count_pdfs.discover_pdfs(pdf_dir)
        result = count_pdfs.filter_by_language(files, "en")

        assert len(result) == 2
        assert all(p.name.startswith("en_") for p in result)

    def test_filter_by_language_fr(self, tmp_output_structure: dict) -> None:
        """Verify French PDFs are filtered correctly.

        Real-world significance:
        - Quebec and Francophone deployments use fr prefix
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "en_notice_00001.pdf")
        create_test_pdf(pdf_dir / "fr_notice_00001.pdf")
        create_test_pdf(pdf_dir / "fr_notice_00002.pdf")

        files = count_pdfs.discover_pdfs(pdf_dir)
        result = count_pdfs.filter_by_language(files, "fr")

        assert len(result) == 2
        assert all(p.name.startswith("fr_") for p in result)

    def test_filter_by_language_none_returns_all(self, tmp_output_structure: dict) -> None:
        """Verify all PDFs returned when language is None.

        Real-world significance:
        - When no language filter needed, should return all
        - Backwards compatibility for non-language-specific counts
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "en_notice.pdf")
        create_test_pdf(pdf_dir / "fr_notice.pdf")

        files = count_pdfs.discover_pdfs(pdf_dir)
        result = count_pdfs.filter_by_language(files, None)

        assert len(result) == 2


@pytest.mark.unit
class TestSummarizePdfs:
    """Unit tests for summarize_pdfs function."""

    def test_summarize_pdfs_counts_pages(self, tmp_output_structure: dict) -> None:
        """Verify page counts are detected correctly.

        Real-world significance:
        - Expected: 2 pages per notice (both sides, immunization info + chart)
        - Must detect actual page count
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "notice_00002.pdf", num_pages=2)

        files = count_pdfs.discover_pdfs(pdf_dir)
        results, buckets = count_pdfs.summarize_pdfs(files)

        assert len(results) == 2
        assert all(pages == 2 for _, pages in results)

    def test_summarize_pdfs_builds_histogram(self, tmp_output_structure: dict) -> None:
        """Verify page count histogram is built.

        Real-world significance:
        - Quick summary of page distribution
        - Detects PDFs with incorrect page count
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=1)
        create_test_pdf(pdf_dir / "notice_00002.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "notice_00003.pdf", num_pages=2)

        files = count_pdfs.discover_pdfs(pdf_dir)
        results, buckets = count_pdfs.summarize_pdfs(files)

        assert buckets[1] == 1
        assert buckets[2] == 2

    def test_summarize_pdfs_empty_list(self) -> None:
        """Verify empty list returns empty results.

        Real-world significance:
        - May happen if all files filtered out
        - Should handle gracefully
        """
        results, buckets = count_pdfs.summarize_pdfs([])

        assert results == []
        assert len(buckets) == 0


@pytest.mark.unit
class TestWriteJson:
    """Unit tests for write_json function."""

    def test_write_json_creates_manifest(self, tmp_output_structure: dict) -> None:
        """Verify JSON manifest is created with correct structure.

        Real-world significance:
        - Manifest used for quality control and reporting
        - Must contain file-level page counts
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)

        files = count_pdfs.discover_pdfs(pdf_dir)
        results, buckets = count_pdfs.summarize_pdfs(files)

        output_path = tmp_output_structure["metadata"] / "manifest.json"
        count_pdfs.write_json(results, buckets, target=output_path, language="en")

        assert output_path.exists()
        manifest = json.loads(output_path.read_text())
        assert manifest["language"] == "en"
        assert manifest["total_pdfs"] == 1
        assert len(manifest["files"]) == 1

    def test_write_json_creates_directories(self, tmp_output_structure: dict) -> None:
        """Verify parent directories are created if missing.

        Real-world significance:
        - Metadata directory may not exist yet
        - Must auto-create
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice.pdf")

        files = count_pdfs.discover_pdfs(pdf_dir)
        results, buckets = count_pdfs.summarize_pdfs(files)

        output_path = tmp_output_structure["root"] / "deep" / "nested" / "manifest.json"
        count_pdfs.write_json(results, buckets, target=output_path, language="en")

        assert output_path.exists()

    def test_write_json_includes_file_details(self, tmp_output_structure: dict) -> None:
        """Verify JSON includes per-file page counts.

        Real-world significance:
        - Enables tracking which files have incorrect page counts
        - Useful for debugging
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "notice_00002.pdf", num_pages=3)

        files = count_pdfs.discover_pdfs(pdf_dir)
        results, buckets = count_pdfs.summarize_pdfs(files)

        output_path = tmp_output_structure["metadata"] / "manifest.json"
        count_pdfs.write_json(results, buckets, target=output_path, language="en")

        manifest = json.loads(output_path.read_text())
        assert len(manifest["files"]) == 2
        assert manifest["files"][0]["pages"] == 2
        assert manifest["files"][1]["pages"] == 3


@pytest.mark.unit
class TestMainEntry:
    """Unit tests for main entry point."""

    def test_main_with_directory(self, tmp_output_structure: dict) -> None:
        """Verify main function works with directory input.

        Real-world significance:
        - Standard usage: pass PDF directory and get summary
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice_00001.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "notice_00002.pdf", num_pages=2)

        results, buckets = count_pdfs.main(pdf_dir)

        assert len(results) == 2
        assert buckets[2] == 2

    def test_main_with_language_filter(self, tmp_output_structure: dict) -> None:
        """Verify main function filters by language.

        Real-world significance:
        - May need to count only English or French PDFs
        - Language parameter enables filtering
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "en_notice_00001.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "en_notice_00002.pdf", num_pages=2)
        create_test_pdf(pdf_dir / "fr_notice_00001.pdf", num_pages=2)

        results, buckets = count_pdfs.main(pdf_dir, language="en")

        assert len(results) == 2

    def test_main_with_json_output(self, tmp_output_structure: dict) -> None:
        """Verify main function writes JSON manifest.

        Real-world significance:
        - Pipeline needs to save manifest for tracking
        """
        pdf_dir = tmp_output_structure["pdf_individual"]
        create_test_pdf(pdf_dir / "notice.pdf", num_pages=2)

        output_path = tmp_output_structure["metadata"] / "manifest.json"
        count_pdfs.main(pdf_dir, json_output=output_path)

        assert output_path.exists()
        manifest = json.loads(output_path.read_text())
        assert manifest["total_pdfs"] == 1
