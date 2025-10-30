"""Validate compiled PDFs for layout, structure, and quality issues.

Performs comprehensive validation of compiled PDF files including page counts,
layout checks (signature placement), and structural integrity. Outputs validation
results to JSON metadata for downstream processing and optional console warnings.

**Input Contract:**
- Reads PDF files from output/pdf_individual/ directory
- Assumes PDFs are valid (created by compilation step)
- Assumes each PDF corresponds to one client notice

**Output Contract:**
- Writes validation results to JSON: output/metadata/{language}_validation_{run_id}.json
- Records per-PDF validations: page counts, layout warnings, structural issues
- Aggregate statistics: total PDFs, warnings by type, pass/fail counts
- Optional console output (controlled by config: pdf_validation.print_warnings)

**Error Handling:**
- Invalid/corrupt PDFs raise immediately (fail-fast; quality validation step)
- Missing PDF files raise immediately (infrastructure error)
- Layout warnings are non-fatal (logged but don't halt pipeline)
- All PDFs must be readable; validation results may contain warnings (quality step)

**Validation Contract:**

What this module validates:
- PDF files are readable and structurally valid (uses PdfReader)
- Page count statistics and distribution
- Layout markers (signature block placement using MARK_END_SIGNATURE_BLOCK)
- Expected vs actual page counts (configurable tolerance)

What this module assumes (validated upstream):
- PDF files exist and are complete (created by compile step)
- PDF filenames match expected pattern (from notice generation)
- Output metadata directory can be created (general I/O)

Note: This is a validation/QA step. Structural PDF errors halt pipeline (fail-fast),
but layout warnings are non-fatal and logged for review.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader


@dataclass
class ValidationResult:
    """Result of validating a single PDF file.

    Attributes
    ----------
    filename : str
        Name of the PDF file
    page_count : int
        Total number of pages in the PDF
    warnings : List[str]
        List of validation warnings (layout issues, unexpected page counts, etc.)
    passed : bool
        True if no warnings, False otherwise
    """

    filename: str
    page_count: int
    warnings: List[str]
    passed: bool


@dataclass
class ValidationSummary:
    """Aggregate validation results for all PDFs.

    Attributes
    ----------
    language : str | None
        Language code if filtered (e.g., 'en' or 'fr')
    total_pdfs : int
        Total number of PDFs validated
    passed_count : int
        Number of PDFs with no warnings
    warning_count : int
        Number of PDFs with warnings
    page_count_distribution : dict[int, int]
        Distribution of page counts (pages -> count)
    warning_types : dict[str, int]
        Count of warnings by type/category
    results : List[ValidationResult]
        Per-file validation results
    """

    language: str | None
    total_pdfs: int
    passed_count: int
    warning_count: int
    page_count_distribution: dict[int, int]
    warning_types: dict[str, int]
    results: List[ValidationResult]


def discover_pdfs(target: Path) -> List[Path]:
    """Discover all PDF files at the given target path.

    Parameters
    ----------
    target : Path
        Either a directory containing PDFs or a single PDF file.

    Returns
    -------
    List[Path]
        Sorted list of PDF file paths.

    Raises
    ------
    FileNotFoundError
        If target is neither a PDF file nor a directory containing PDFs.
    """
    if target.is_dir():
        return sorted(target.glob("*.pdf"))
    if target.is_file() and target.suffix.lower() == ".pdf":
        return [target]
    raise FileNotFoundError(f"No PDF(s) found at {target}")


def filter_by_language(files: List[Path], language: str | None) -> List[Path]:
    """Filter PDF files by language prefix in filename.

    Parameters
    ----------
    files : List[Path]
        PDF file paths to filter.
    language : str | None
        Language code to filter by (e.g., 'en' or 'fr'). If None, returns all files.

    Returns
    -------
    List[Path]
        Filtered list of PDF paths, or all files if language is None.
    """
    if not language:
        return list(files)
    prefix = f"{language}_"
    return [path for path in files if path.name.startswith(prefix)]


def validate_pdf_layout(
    pdf_path: Path, reader: PdfReader, enabled_rules: dict[str, str]
) -> List[str]:
    """Check PDF for layout issues using invisible markers.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file being validated.
    reader : PdfReader
        Opened PDF reader instance.
    enabled_rules : dict[str, str]
        Validation rules configuration (rule_name -> "disabled"/"warn"/"error").

    Returns
    -------
    List[str]
        List of layout warning messages (empty if no issues).
    """
    warnings = []

    # Skip if rule is disabled
    rule_setting = enabled_rules.get("signature_overflow", "warn")
    if rule_setting == "disabled":
        return warnings

    # Check for signature block marker placement
    marker_found = False
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text()
            if "MARK_END_SIGNATURE_BLOCK" in page_text:
                marker_found = True
                if page_num != 1:
                    warnings.append(
                        f"signature_overflow: Signature block found on page {page_num} "
                        f"(expected page 1)"
                    )
                break
        except Exception:
            # If text extraction fails, skip this check
            pass

    if not marker_found:
        # Marker not found - may not be critical but worth noting
        # (older templates may not have markers)
        pass

    return warnings


def validate_pdf_structure(
    pdf_path: Path,
    enabled_rules: dict[str, str] | None = None,
) -> ValidationResult:
    """Validate a single PDF file for structure and layout.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file to validate.
    enabled_rules : dict[str, str], optional
        Validation rules configuration (rule_name -> "disabled"/"warn"/"error").

    Returns
    -------
    ValidationResult
        Validation result with page count, warnings, and pass/fail status.

    Raises
    ------
    Exception
        If PDF cannot be read (structural corruption).
    """
    warnings = []
    if enabled_rules is None:
        enabled_rules = {}

    # Read PDF and count pages
    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    # Check for exactly 2 pages (standard notice format)
    rule_setting = enabled_rules.get("exactly_two_pages", "warn")
    if page_count != 2 and rule_setting != "disabled":
        warnings.append(f"exactly_two_pages: {page_count} pages (expected 2)")

    # Validate layout using markers
    layout_warnings = validate_pdf_layout(pdf_path, reader, enabled_rules)
    warnings.extend(layout_warnings)

    return ValidationResult(
        filename=pdf_path.name,
        page_count=page_count,
        warnings=warnings,
        passed=len(warnings) == 0,
    )


def validate_pdfs(
    files: List[Path],
    enabled_rules: dict[str, str] | None = None,
) -> ValidationSummary:
    """Validate all PDF files and generate summary.

    Parameters
    ----------
    files : List[Path]
        PDF file paths to validate.
    enabled_rules : dict[str, str], optional
        Validation rules configuration (rule_name -> "disabled"/"warn"/"error").

    Returns
    -------
    ValidationSummary
        Aggregate validation results with statistics and per-file details.
    """
    results: List[ValidationResult] = []
    page_buckets: Counter = Counter()
    warning_type_counts: Counter = Counter()

    for pdf_path in files:
        result = validate_pdf_structure(pdf_path, enabled_rules=enabled_rules)
        results.append(result)
        page_buckets[result.page_count] += 1

        # Count warning types
        for warning in result.warnings:
            warning_type = warning.split(":")[0] if ":" in warning else "other"
            warning_type_counts[warning_type] += 1

    passed_count = sum(1 for r in results if r.passed)
    warning_count = len(results) - passed_count

    return ValidationSummary(
        language=None,  # Set by caller
        total_pdfs=len(results),
        passed_count=passed_count,
        warning_count=warning_count,
        page_count_distribution=dict(sorted(page_buckets.items())),
        warning_types=dict(warning_type_counts),
        results=results,
    )


def print_validation_summary(
    summary: ValidationSummary,
    *,
    validation_json_path: Path | None = None,
) -> None:
    """Print human-readable validation summary to console.

    Parameters
    ----------
    summary : ValidationSummary
        Validation summary to print.
    validation_json_path : Path, optional
        Path to validation JSON for reference in output.
    """
    # High-level pass/fail summary
    scope = f"'{summary.language}' " if summary.language else ""
    passed_label = "PDF" if summary.passed_count == 1 else "PDFs"
    failed_label = "PDF" if summary.warning_count == 1 else "PDFs"

    print(f"Validated {summary.total_pdfs} {scope}PDF(s):")
    print(f"  ✅ {summary.passed_count} {passed_label} passed")

    if summary.warning_count > 0:
        print(f"  ⚠️  {summary.warning_count} {failed_label} with warnings")

        # Per-rule summary
        print("\nValidation warnings by rule:")
        for warning_type, count in sorted(summary.warning_types.items()):
            rule_label = "PDF" if count == 1 else "PDFs"
            print(f"  - {warning_type}: {count} {rule_label}")

        # Reference to detailed log
        if validation_json_path:
            print(
                f"\nDetailed validation results: {validation_json_path.relative_to(Path.cwd())}"
            )


def write_validation_json(summary: ValidationSummary, output_path: Path) -> None:
    """Write validation summary to JSON file.

    Parameters
    ----------
    summary : ValidationSummary
        Validation summary to serialize.
    output_path : Path
        Path to output JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and serialize
    payload = asdict(summary)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def check_for_errors(
    summary: ValidationSummary, enabled_rules: dict[str, str]
) -> List[str]:
    """Check if any validation rules are set to 'error' and have failures.

    Parameters
    ----------
    summary : ValidationSummary
        Validation summary with warning counts by type.
    enabled_rules : dict[str, str]
        Validation rules configuration (rule_name -> "disabled"/"warn"/"error").

    Returns
    -------
    List[str]
        List of error messages for rules that failed with severity 'error'.
    """
    errors = []
    for rule_name, severity in enabled_rules.items():
        if severity == "error" and rule_name in summary.warning_types:
            count = summary.warning_types[rule_name]
            label = "PDF" if count == 1 else "PDFs"
            errors.append(f"{rule_name}: {count} {label} failed validation")
    return errors


def main(
    target: Path,
    language: str | None = None,
    enabled_rules: dict[str, str] | None = None,
    json_output: Path | None = None,
) -> ValidationSummary:
    """Main entry point for PDF validation.

    Parameters
    ----------
    target : Path
        PDF file or directory containing PDFs.
    language : str, optional
        Optional language prefix to filter PDF filenames (e.g., 'en').
    enabled_rules : dict[str, str], optional
        Validation rules configuration (rule_name -> "disabled"/"warn"/"error").
    json_output : Path, optional
        Optional path to write validation summary as JSON.

    Returns
    -------
    ValidationSummary
        Validation summary with all results and statistics.

    Raises
    ------
    RuntimeError
        If any validation rule with severity 'error' fails.
    """
    if enabled_rules is None:
        enabled_rules = {}

    files = discover_pdfs(target)
    filtered = filter_by_language(files, language)
    summary = validate_pdfs(filtered, enabled_rules=enabled_rules)
    summary.language = language

    if json_output:
        write_validation_json(summary, json_output)

    # Always print summary
    print_validation_summary(summary, validation_json_path=json_output)

    # Check for error-level failures
    errors = check_for_errors(summary, enabled_rules)
    if errors:
        error_msg = "PDF validation failed with errors:\n  " + "\n  ".join(errors)
        raise RuntimeError(error_msg)

    return summary


if __name__ == "__main__":
    import sys

    print(
        "⚠️  Direct invocation: This module is typically executed via orchestrator.py.\n"
        "   Re-running a single step is valid when pipeline artifacts are retained on disk,\n"
        "   allowing you to skip earlier steps and regenerate output.\n"
        "   Note: Output will overwrite any previous files.\n"
        "\n"
        "   For typical usage, run: uv run viper <input> <language>\n",
        file=sys.stderr,
    )
    sys.exit(1)
