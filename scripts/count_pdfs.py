"""Summarize page counts for PDFs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Tuple

from pypdf import PdfReader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize page counts for PDFs.")
    parser.add_argument(
        "target",
        type=Path,
        help="PDF file or directory containing PDFs.",
    )
    parser.add_argument(
        "--language",
        help="Optional language prefix to filter PDF filenames (e.g., 'en').",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file page counts instead of summary only.",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        type=Path,
        help="Optional path to write the summary as JSON.",
    )
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    files = discover_pdfs(args.target)
    filtered = filter_by_language(files, args.language)
    results, buckets = summarize_pdfs(filtered)
    print_summary(results, buckets, language=args.language, verbose=args.verbose)
    if args.json_output:
        write_json(results, buckets, target=args.json_output, language=args.language)


if __name__ == "__main__":
    main()
