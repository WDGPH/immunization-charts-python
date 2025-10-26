"""Encryption module for immunization PDF notices.

This module provides functions to encrypt PDF notices using client metadata.
It's designed to be integrated into the pipeline as an optional step.

Passwords are generated per-client per-PDF using templates defined in
config/parameters.yaml under encryption.password.template. Templates support
placeholders like {client_id}, {date_of_birth_iso}, {date_of_birth_iso_compact},
{first_name}, {last_name}, {school}, {postal_code}, etc.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Tuple

import yaml
from pypdf import PdfReader, PdfWriter

from .enums import TemplateField
from .utils import build_client_context, validate_and_format_template

# Configuration paths
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

_encryption_config = None


def _load_encryption_config():
    """Load and cache encryption configuration from parameters.yaml.

    Configuration is loaded once and cached globally for subsequent function calls.
    This avoids repeated file I/O when generating passwords for multiple PDFs.

    Returns
    -------
    dict
        Encryption configuration dict (typically contains 'password' key with
        'template' sub-key), or empty dict if config file not found.
    """
    global _encryption_config
    if _encryption_config is None:
        try:
            parameters_path = CONFIG_DIR / "parameters.yaml"
            if parameters_path.exists():
                with open(parameters_path) as f:
                    params = yaml.safe_load(f) or {}
                    _encryption_config = params.get("encryption", {})
            else:
                _encryption_config = {}
        except Exception:
            _encryption_config = {}
    return _encryption_config


def get_encryption_config():
    """Get the encryption configuration from parameters.yaml.

    Returns
    -------
    dict
        Cached encryption configuration.
    """
    return _load_encryption_config()


def encrypt_pdf(
    file_path: str, context_or_oen: str | dict, dob: str | None = None
) -> str:
    """Encrypt a PDF with a password derived from client context.

    Supports two calling patterns:
    1. New (recommended): encrypt_pdf(file_path, context_dict)
    2. Legacy: encrypt_pdf(file_path, oen_partial, dob)

    Parameters
    ----------
    file_path : str
        Path to the PDF file to encrypt.
    context_or_oen : str | dict
        Either:
        - A dict with template context (from build_client_context)
        - A string client identifier (legacy mode)
    dob : str | None
        Date of birth in YYYY-MM-DD format (required if context_or_oen is str).

    Returns
    -------
    str
        Path to the encrypted PDF file with _encrypted suffix.
    """
    # Handle both new (context dict) and legacy (oen + dob) calling patterns
    if isinstance(context_or_oen, dict):
        context = context_or_oen
        config = get_encryption_config()
        password_config = config.get("password", {})
        template = password_config.get("template", "{date_of_birth_iso_compact}")
        try:
            password = validate_and_format_template(
                template, context, allowed_fields=TemplateField.all_values()
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid password template: {e}") from e
    else:
        # Legacy mode: context_or_oen is oen_partial
        if dob is None:
            raise ValueError("dob must be provided when context_or_oen is a string")
        config = get_encryption_config()
        password_config = config.get("password", {})
        template = password_config.get("template", "{date_of_birth_iso_compact}")
        context = {
            "client_id": str(context_or_oen),
            "date_of_birth_iso": str(dob),
            "date_of_birth_iso_compact": str(dob).replace("-", ""),
        }
        try:
            password = validate_and_format_template(
                template, context, allowed_fields=TemplateField.all_values()
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid password template: {e}") from e

    reader = PdfReader(file_path, strict=False)
    writer = PdfWriter()

    # Use pypdf's standard append method (pinned via uv.lock)
    writer.append(reader)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    writer.encrypt(user_password=password, owner_password=password)

    src = Path(file_path)
    encrypted_path = src.with_name(f"{src.stem}_encrypted{src.suffix}")
    with open(encrypted_path, "wb") as f:
        writer.write(f)

    return str(encrypted_path)


def _load_notice_metadata(json_path: Path, language: str) -> tuple:
    """Load client data and context from JSON notice metadata.

    Returns both the client data dict and the context for password template rendering.
    """
    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON structure ({json_path.name}): {exc}") from exc

    if not payload:
        raise ValueError(f"No client data in {json_path.name}")

    first_key = next(iter(payload))
    record = payload[first_key]

    # Ensure record has required fields for context building
    if not isinstance(record, dict):
        raise ValueError(f"Invalid client record format in {json_path.name}")

    context = build_client_context(record, language)
    return record, context


def encrypt_notice(json_path: str | Path, pdf_path: str | Path, language: str) -> str:
    """Encrypt a PDF notice using client data from the JSON file.

    Returns the path to the encrypted PDF with _encrypted suffix.
    If the encrypted version already exists and is newer than the source,
    returns the existing file without re-encrypting.

    Args:
        json_path: Path to the JSON file containing client metadata
        pdf_path: Path to the PDF file to encrypt
        language: ISO 639-1 language code ('en' for English, 'fr' for French)

    Returns:
        Path to the encrypted PDF file

    Raises:
        FileNotFoundError: If JSON or PDF file not found
        ValueError: If JSON is invalid
    """
    json_path = Path(json_path)
    pdf_path = Path(pdf_path)

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

    client_data, context = _load_notice_metadata(json_path, language)
    return encrypt_pdf(str(pdf_path), context)


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
        language: ISO 639-1 language code ('en' for English, 'fr' for French)

    Raises:
        FileNotFoundError: If PDF directory or JSON file don't exist
    """
    pdf_directory = Path(pdf_directory)
    json_file = Path(json_file)

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

        # Build password template context from client metadata
        try:
            context = build_client_context(client_data, language)
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

            encrypt_pdf(str(pdf_path), context)
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
