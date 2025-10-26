"""Summarize page counts for PDFs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Tuple

from pypdf import PdfReader


def discover_pdfs(target: Path) -> List[Path]:
    if target.is_dir():
        return sorted(target.glob("*.pdf"))
    if target.is_file() and target.suffix.lower() == ".pdf":
        return [target]
    raise FileNotFoundError(f"No PDF(s) found at {target}")


def filter_by_language(files: Iterable[Path], language: str | None) -> List[Path]:
    if not language:
        return list(files)
    prefix = f"{language}_"
    return [path for path in files if path.name.startswith(prefix)]


def summarize_pdfs(files: Iterable[Path]) -> Tuple[List[Tuple[Path, int]], Counter]:
    results: List[Tuple[Path, int]] = []
    buckets: Counter = Counter()
    for path in files:
        reader = PdfReader(str(path))
        pages = len(reader.pages)
        results.append((path, pages))
        buckets[pages] += 1
    return results, buckets


def print_summary(
    results: List[Tuple[Path, int]],
    buckets: Counter,
    *,
    language: str | None,
    verbose: bool,
) -> None:
    total = len(results)
    if total == 0:
        scope = f" for language '{language}'" if language else ""
        print(f"No PDFs found{scope}.")
        return

    if verbose:
        for path, pages in results:
            print(f"{path} -> {pages} page(s)")

    scope = f" for language '{language}'" if language else ""
    print(f"Analyzed {total} PDF(s){scope}.")
    for pages in sorted(buckets):
        count = buckets[pages]
        label = "PDF" if count == 1 else "PDFs"
        print(f"  - {count} {label} with {pages} page(s)")

    over_two = sum(count for pages, count in buckets.items() if pages > 2)
    if over_two:
        print(f"⚠️  {over_two} PDF(s) exceed the expected 2-page length.")


def write_json(
    results: List[Tuple[Path, int]],
    buckets: Counter,
    *,
    target: Path,
    language: str | None,
) -> None:
    payload = {
        "language": language,
        "total_pdfs": len(results),
        "buckets": {str(pages): count for pages, count in sorted(buckets.items())},
        "files": [
            {
                "path": str(path),
                "pages": pages,
            }
            for path, pages in results
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(
    target: Path,
    language: str | None = None,
    verbose: bool = False,
    json_output: Path | None = None,
) -> Tuple[List[Tuple[Path, int]], Counter]:
    """Main entry point for PDF counting and validation.

    Parameters
    ----------
    target : Path
        PDF file or directory containing PDFs.
    language : str, optional
        Optional language prefix to filter PDF filenames (e.g., 'en').
    verbose : bool, optional
        Print per-file page counts instead of summary only.
    json_output : Path, optional
        Optional path to write the summary as JSON.

    Returns
    -------
    Tuple[List[Tuple[Path, int]], Counter]
        Results and bucket counts from summarization.
    """
    files = discover_pdfs(target)
    filtered = filter_by_language(files, language)
    results, buckets = summarize_pdfs(filtered)
    print_summary(results, buckets, language=language, verbose=verbose)
    if json_output:
        write_json(results, buckets, target=json_output, language=language)
    return results, buckets


if __name__ == "__main__":
    raise RuntimeError(
        "count_pdfs.py should not be invoked directly. Use orchestrator.py instead."
    )
