import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from utils import encrypt_pdf, convert_date


def _normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    if normalized not in {"english", "french"}:
        raise ValueError("Language must be 'english' or 'french'")
    return normalized


def _load_notice_metadata(json_path: Path, language: str) -> Tuple[str, str]:
    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON structure ({json_path.name}): {exc}") from exc

    if not payload:
        raise ValueError(f"No client data in {json_path.name}")

    first_key = next(iter(payload))
    record = payload[first_key]
    client_id = record.get("client_id", first_key)

    dob_iso: Optional[str] = record.get("date_of_birth_iso")
    if not dob_iso:
        dob_display = record.get("date_of_birth")
        if not dob_display:
            raise ValueError(f"Missing date of birth in {json_path.name}")
        dob_iso = convert_date(
            dob_display,
            to_format="iso",
            lang="fr" if language == "french" else "en",
        )

    return str(client_id), dob_iso


def encrypt_notice(json_path: str | Path, pdf_path: str | Path, language: str) -> str:
    """
    Encrypt a PDF notice using client data from the JSON file. Returns the
    path to the encrypted PDF.
    """
    json_path = Path(json_path)
    pdf_path = Path(pdf_path)
    language = _normalize_language(language)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    encrypted_path = pdf_path.with_name(f"{pdf_path.stem}_encrypted{pdf_path.suffix}")
    if encrypted_path.exists():
        try:
            if encrypted_path.stat().st_mtime >= pdf_path.stat().st_mtime:
                return str(encrypted_path)
        except OSError:
            pass

    client_id, dob_iso = _load_notice_metadata(json_path, language)
    return encrypt_pdf(str(pdf_path), str(client_id), dob_iso)


def _discover_notice_pairs(directory: Path) -> Tuple[List[Tuple[Path, Path]], List[str]]:
    pairs: List[Tuple[Path, Path]] = []
    missing_json: List[str] = []

    for pdf_path in sorted(directory.glob("*.pdf")):
        stem = pdf_path.stem
        if stem == "conf" or stem.endswith("_encrypted"):
            continue

        base_name = stem
        if base_name.endswith("_immunization_notice"):
            base_name = base_name[: -len("_immunization_notice")]

        json_path = pdf_path.with_name(f"{base_name}.json")
        if not json_path.exists():
            missing_json.append(pdf_path.name)
            continue

        pairs.append((json_path, pdf_path))

    return pairs, missing_json


def _resolve_worker_count(requested: Optional[int], job_count: int) -> int:
    if job_count <= 0:
        return 0
    if requested is not None:
        if requested <= 0:
            raise ValueError("Number of workers must be a positive integer.")
        return max(1, min(requested, job_count))
    cpu_default = os.cpu_count() or 1
    return max(1, min(cpu_default, job_count))


def _run_jobs(
    jobs: List[Tuple[str, str, str]],
    worker_count: int,
    chunk_size: int,
) -> Iterator[Tuple[str, str, str]]:
    if worker_count <= 1:
        for job in jobs:
            yield _job(job)
        return

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        for result in executor.map(_job, jobs, chunksize=chunk_size):
            yield result


def _job(args: Tuple[str, str, str]) -> Tuple[str, str, str]:
    json_path_str, pdf_path_str, language = args
    try:
        encrypt_notice(json_path_str, pdf_path_str, language)
        return ("ok", pdf_path_str, "")
    except (FileNotFoundError, ValueError) as exc:
        return ("skipped", pdf_path_str, str(exc))
    except Exception as exc:  # pragma: no cover - unexpected errors
        return ("error", pdf_path_str, str(exc))


def batch_encrypt(
    directory: Path,
    language: str,
    workers: Optional[int] = None,
    chunk_size: int = 4,
) -> None:
    directory = Path(directory)
    language = _normalize_language(language)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    pairs, missing_json = _discover_notice_pairs(directory)

    if missing_json:
        for pdf_name in missing_json:
            print(f"WARNING: Missing JSON partner for {pdf_name}; skipping.")

    if not pairs:
        print("No notices found for encryption.")
        return

    jobs: List[Tuple[str, str, str]] = [
        (str(json_path), str(pdf_path), language) for json_path, pdf_path in pairs
    ]
    worker_count = _resolve_worker_count(workers, len(jobs))
    chunk_size = max(1, chunk_size)

    start = time.perf_counter()
    print(
        f"🔐 Encrypting {len(jobs)} notices using {worker_count} worker(s)...",
        flush=True,
    )

    successes = 0
    skipped: List[Tuple[str, str]] = []
    failures: List[Tuple[str, str]] = []

    for status, pdf_path_str, message in _run_jobs(jobs, worker_count, chunk_size):
        pdf_name = Path(pdf_path_str).name
        if status == "ok":
            successes += 1
        elif status == "skipped":
            skipped.append((pdf_name, message))
        else:
            failures.append((pdf_name, message))

    duration = time.perf_counter() - start
    print(
        f"✅ Encryption complete in {duration:.2f}s "
        f"(success: {successes}, skipped: {len(skipped)}, failed: {len(failures)})"
    )

    for pdf_name, reason in skipped:
        print(f"SKIP: {pdf_name} -> {reason}")

    for pdf_name, reason in failures:
        print(f"WARNING: Encryption failed for {pdf_name}: {reason}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Encrypt immunization notices, optionally in parallel batches.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        help="Directory containing JSON/PDF notices for batch encryption.",
    )
    parser.add_argument(
        "--language",
        "-l",
        type=str,
        choices=("english", "french"),
        help="Language of the notices when running in batch mode.",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        help="Number of worker processes to use for batch encryption.",
    )
    parser.add_argument(
        "--chunk-size",
        "-c",
        type=int,
        default=4,
        help="Chunk size to distribute work items to the process pool.",
    )
    parser.add_argument("json_path", nargs="?")
    parser.add_argument("pdf_path", nargs="?")
    parser.add_argument("language_positional", nargs="?")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.directory:
        if args.json_path or args.pdf_path:
            parser.error("Positional JSON/PDF arguments are not allowed with --directory.")
        language = args.language or args.language_positional
        if not language:
            parser.error("Language is required for batch mode. Use --language <english|french>.")
        batch_encrypt(Path(args.directory), language, args.workers, args.chunk_size)
        return

    json_path = args.json_path
    pdf_path = args.pdf_path
    language = args.language_positional or args.language

    if not (json_path and pdf_path and language):
        parser.print_usage()
        print(
            "\nExamples:\n"
            "  encrypt_notice.py notice.json notice.pdf english\n"
            "  encrypt_notice.py --directory ../output/json_english --language english\n"
            "  encrypt_notice.py -d ../output/json_french -l french --workers 4\n"
        )
        sys.exit(1)

    try:
        encrypt_notice(json_path, pdf_path, language)
    except Exception as exc:
        print(f"WARNING: Encryption failed for {Path(pdf_path).name}: {exc}")


if __name__ == "__main__":
    main()
