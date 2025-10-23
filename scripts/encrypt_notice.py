"""Encryption module for immunization PDF notices.

This module provides functions to encrypt PDF notices using client metadata.
It's designed to be integrated into the pipeline as an optional step.
"""

import json
import time
from pathlib import Path
from typing import List, Tuple

try:  # Allow both package and script style execution
    from .utils import encrypt_pdf, convert_date
except ImportError:  # pragma: no cover - fallback for CLI execution
    from utils import encrypt_pdf, convert_date


def _normalize_language(language: str) -> str:
    """Validate and normalize language parameter."""
    normalized = language.strip().lower()
    if normalized not in {"english", "french"}:
        raise ValueError("Language must be 'english' or 'french'")
    return normalized


def _load_notice_metadata(json_path: Path, language: str) -> Tuple[str, str]:
    """Load client ID and DOB from JSON notice metadata."""
    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON structure ({json_path.name}): {exc}") from exc

    if not payload:
        raise ValueError(f"No client data in {json_path.name}")

    first_key = next(iter(payload))
    record = payload[first_key]
    client_id = record.get("client_id", first_key)

    dob_iso: str | None = record.get("date_of_birth_iso")
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
    """Encrypt a PDF notice using client data from the JSON file.

    Returns the path to the encrypted PDF with _encrypted suffix.
    If the encrypted version already exists and is newer than the source,
    returns the existing file without re-encrypting.

    Args:
        json_path: Path to the JSON file containing client metadata
        pdf_path: Path to the PDF file to encrypt
        language: Language code ('english' or 'french')

    Returns:
        Path to the encrypted PDF file

    Raises:
        FileNotFoundError: If JSON or PDF file not found
        ValueError: If JSON is invalid or language is not supported
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


def encrypt_pdfs_in_directory(
    pdf_directory: Path,
    json_file: Path,
    language: str,
) -> None:
    """Encrypt all PDF notices in a directory using a combined JSON metadata file.

    The JSON file should contain a dict where keys are client identifiers and
    values contain client metadata with DOB information.

    PDFs are encrypted in-place with the _encrypted suffix added to filename.

    Args:
        pdf_directory: Directory containing PDF files to encrypt
        json_file: Path to the combined JSON file with all client metadata
        language: Language code ('english' or 'french')

    Raises:
        FileNotFoundError: If PDF directory or JSON file don't exist
        ValueError: If language is not supported
    """
    pdf_directory = Path(pdf_directory)
    json_file = Path(json_file)
    language = _normalize_language(language)

    if not pdf_directory.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_directory}")
    if not json_file.exists():
        raise FileNotFoundError(f"JSON file not found: {json_file}")

    # Load the combined metadata
    try:
        metadata = json.loads(json_file.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {json_file.name}: {exc}") from exc

    # Extract clients from the metadata
    # Handle both preprocessed artifact format (has 'clients' key) and dict of clients
    if isinstance(metadata, dict) and "clients" in metadata:
        clients_data = metadata["clients"]
    else:
        clients_data = metadata

    if not clients_data:
        print("No client data found in JSON file.")
        return

    # Build a lookup dict: client_id -> client_data
    client_lookup = {}
    if isinstance(clients_data, list):
        # Format: list of client dicts with 'client_id' field
        for client in clients_data:
            client_id = client.get("client_id")
            if client_id:
                client_lookup[str(client_id)] = client
    elif isinstance(clients_data, dict):
        # Format: dict keyed by client_id
        client_lookup = {str(k): v for k, v in clients_data.items()}

    # Find PDFs and encrypt them
    pdf_files = sorted(pdf_directory.glob("*.pdf"))
    if not pdf_files:
        print("No PDFs found for encryption.")
        return

    start = time.perf_counter()
    print(
        f"🔐 Encrypting {len(pdf_files)} notices...",
        flush=True,
    )

    successes = 0
    skipped: List[Tuple[str, str]] = []
    failures: List[Tuple[str, str]] = []

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        stem = pdf_path.stem

        # Skip conf and already-encrypted files
        if stem == "conf" or stem.endswith("_encrypted"):
            continue

        # Extract client_id from filename (format: en_client_XXXXX_YYYYYYY)
        # The last part after the last underscore is the client_id (OEN)
        parts = stem.split("_")
        if len(parts) >= 3:
            client_id = parts[-1]
        else:
            skipped.append((pdf_name, "Could not extract client_id from filename"))
            continue

        # Look up client data
        client_data = client_lookup.get(client_id)
        if not client_data:
            skipped.append((pdf_name, f"No metadata found for client_id {client_id}"))
            continue

        # Get DOB - handle nested structure (preprocessed artifact format)
        dob_iso = None
        if isinstance(client_data, dict):
            # Try nested format first (person.date_of_birth_iso)
            if "person" in client_data and isinstance(client_data["person"], dict):
                dob_iso = client_data["person"].get("date_of_birth_iso")
            # Fall back to flat format
            if not dob_iso:
                dob_iso = client_data.get("date_of_birth_iso")

        if not dob_iso:
            # Try to get display format and convert
            dob_display = None
            if isinstance(client_data, dict):
                if "person" in client_data and isinstance(client_data["person"], dict):
                    dob_display = client_data["person"].get("date_of_birth_display")
                if not dob_display:
                    dob_display = client_data.get("date_of_birth")

            if not dob_display:
                skipped.append((pdf_name, "Missing date of birth in metadata"))
                continue

            try:
                dob_iso = convert_date(
                    dob_display,
                    to_format="iso",
                    lang="fr" if language == "french" else "en",
                )
            except ValueError as exc:
                skipped.append((pdf_name, str(exc)))
                continue

        # Encrypt the PDF
        try:
            encrypted_path = pdf_path.with_name(
                f"{pdf_path.stem}_encrypted{pdf_path.suffix}"
            )

            # Skip if encrypted version is newer than source
            if encrypted_path.exists():
                try:
                    if encrypted_path.stat().st_mtime >= pdf_path.stat().st_mtime:
                        successes += 1
                        continue
                except OSError:
                    pass

            encrypt_pdf(str(pdf_path), str(client_id), dob_iso)
            # Delete the unencrypted version after successful encryption
            try:
                pdf_path.unlink()
            except OSError as e:
                print(f"Warning: Could not delete unencrypted PDF {pdf_name}: {e}")
            successes += 1
        except Exception as exc:
            failures.append((pdf_name, str(exc)))

    duration = time.perf_counter() - start
    print(
        f"✅ Encryption complete in {duration:.2f}s "
        f"(success: {successes}, skipped: {len(skipped)}, failed: {len(failures)})"
    )

    for pdf_name, reason in skipped:
        print(f"SKIP: {pdf_name} -> {reason}")

    for pdf_name, reason in failures:
        print(f"WARNING: Encryption failed for {pdf_name}: {reason}")
