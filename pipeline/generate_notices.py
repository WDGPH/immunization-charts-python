"""Generate per-client Typst notices from the normalized preprocessing artifact.

This module consumes the JSON artifact emitted by ``preprocess.py`` and generates
per-client Typst templates for notice rendering.

**Input Contract:**
- Reads preprocessed artifact JSON (created by preprocess step)
- Assumes artifact contains valid client records with all required fields
- Assumes language validation already occurred at CLI entry point

**Output Contract:**
- Writes per-client Typst template files to output/artifacts/typst/
- Returns list of successfully generated .typ file paths
- All clients must succeed; fails immediately on first error (critical feature)

**Error Handling:**
- Client data errors raise immediately (cannot produce incomplete output)
- Infrastructure errors (missing paths) raise immediately
- Invalid language enum raises immediately (should never occur if upstream validates)
- No per-client recovery; fail-fast approach ensures deterministic output

**Validation Contract:**

What this module validates:
- Artifact language matches all client languages (fail-fast if mismatch)

What this module assumes (validated upstream):
- Artifact file exists and is valid JSON (validated by read_artifact())
- Language code is valid (validated at CLI by argparse choices)
- Client records have all required fields (validated by preprocessing step)
- File paths exist (output_dir, logo_path, signature_path, parameters_path)

Functions with special validation notes:
- render_notice(): Calls Language.from_string() on client.language to convert
  string to enum; this adds a second validation layer (redundant but safe)
- get_language_renderer(): Assumes language enum is valid; no defensive check
  (language validated upstream via CLI choices + Language.from_string())
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from .data_models import (
    ArtifactPayload,
    ClientRecord,
)
from .enums import Language
from .translation_helpers import display_label

from templates.en_template import render_notice as render_notice_en
from templates.fr_template import render_notice as render_notice_fr

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Build renderer dict from Language enum
_LANGUAGE_RENDERERS = {
    Language.ENGLISH.value: render_notice_en,
    Language.FRENCH.value: render_notice_fr,
}


def get_language_renderer(language: Language):
    """Get template renderer for given language.

    Maps Language enum values to their corresponding template rendering functions.
    This provides a single, extensible dispatch point for template selection.

    **Validation Contract:** Assumes language is a valid Language enum (validated
    upstream at CLI entry point via argparse choices, and again by Language.from_string()
    before calling this function). No defensive validation needed.

    Parameters
    ----------
    language : Language
        Language enum value (guaranteed to be valid from Language enum).

    Returns
    -------
    callable
        Template rendering function for the language.

    Examples
    --------
    >>> renderer = get_language_renderer(Language.ENGLISH)
    >>> # renderer is now render_notice_en function
    """
    # Language is already validated upstream (CLI choices + Language.from_string())
    # Direct lookup; safe because only valid Language enums reach this function
    return _LANGUAGE_RENDERERS[language.value]


def read_artifact(path: Path) -> ArtifactPayload:
    """Read and deserialize the preprocessed artifact JSON.

    **Input Contract:** Assumes artifact was created by preprocessing step and
    contains valid client records. Does not validate client schema; relies on
    preprocessing to have ensured data quality.

    Parameters
    ----------
    path : Path
        Path to the preprocessed artifact JSON file.

    Returns
    -------
    ArtifactPayload
        Parsed artifact with clients and metadata.

    Raises
    ------
    FileNotFoundError
        If artifact file does not exist.
    json.JSONDecodeError
        If artifact is not valid JSON.
    KeyError
        If artifact is missing required fields.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Preprocessed artifact not found: {path}. "
            "Ensure preprocessing step has completed."
        )

    try:
        payload_dict = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Preprocessed artifact is not valid JSON: {path}") from exc

    clients = []

    for client_dict in payload_dict["clients"]:
        client = ClientRecord(
            sequence=client_dict["sequence"],
            client_id=client_dict["client_id"],
            language=client_dict["language"],
            person=client_dict["person"],
            school=client_dict["school"],
            board=client_dict["board"],
            contact=client_dict["contact"],
            vaccines_due=client_dict.get("vaccines_due"),
            vaccines_due_list=client_dict.get("vaccines_due_list"),
            received=client_dict.get("received"),
            metadata=client_dict.get("metadata", {}),
            qr=client_dict.get("qr"),
        )
        clients.append(client)

    return ArtifactPayload(
        run_id=payload_dict["run_id"],
        language=payload_dict["language"],
        clients=clients,
        warnings=payload_dict.get("warnings", []),
        created_at=payload_dict.get("created_at", ""),
        total_clients=payload_dict.get("total_clients", len(clients)),
    )


def escape_string(value: str) -> str:
    """Escape special characters in a string for Typst template output.

    Module-internal helper for to_typ_value(). Escapes backslashes, quotes,
    and newlines to ensure the string can be safely embedded in a Typst template.

    Parameters
    ----------
    value : str
        String to escape.

    Returns
    -------
    str
        Escaped string safe for Typst embedding.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_typ_value(value) -> str:
    """Convert a Python value to its Typst template representation.

    Module-internal helper for building template contexts. Handles strings
    (with escaping), booleans, None, numbers, sequences (tuples), and mappings
    (dicts) by converting them to Typst syntax.

    Parameters
    ----------
    value : Any
        Python value to convert.

    Returns
    -------
    str
        Typst-compatible representation of the value.

    Raises
    ------
    TypeError
        If value type is not supported.

    Examples
    --------
    >>> to_typ_value("hello")
    '"hello"'
    >>> to_typ_value(True)
    'true'
    >>> to_typ_value([1, 2, 3])
    '(1, 2, 3)'
    """
    if isinstance(value, str):
        return f'"{escape_string(value)}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [to_typ_value(item) for item in value]
        if len(items) == 1:
            inner = f"{items[0]},"
        else:
            inner = ", ".join(items)
        return f"({inner})"
    if isinstance(value, Mapping):
        items = ", ".join(f"{key}: {to_typ_value(val)}" for key, val in value.items())
        return f"({items})"
    raise TypeError(f"Unsupported value type for Typst conversion: {type(value)!r}")


def build_template_context(
    client: ClientRecord, qr_output_dir: Path | None = None
) -> Dict[str, str]:
    """Build template context from client data.

    Translates disease names in vaccines_due_list and received records to
    localized display strings using the configured translation files.

    Parameters
    ----------
    client : ClientRecord
        Client record with all required fields.
    qr_output_dir : Path, optional
        Directory containing QR code PNG files.

    Returns
    -------
    Dict[str, str]
        Template context with translated disease names.
    """
    client_data = {
        "name": client.person["full_name"],
        "address": client.contact["street"],
        "city": client.contact["city"],
        "postal_code": client.contact["postal_code"],
        "date_of_birth": client.person["date_of_birth_display"],
        "school": client.school["name"],
    }

    # Check if QR code PNG exists from prior generation step
    if qr_output_dir:
        qr_filename = f"qr_code_{client.sequence}_{client.client_id}.png"
        qr_path = qr_output_dir / qr_filename
        if qr_path.exists():
            client_data["qr_code"] = to_root_relative(qr_path)

    # Translate vaccines_due_list to display labels
    vaccines_due_array_translated: List[str] = []
    if client.vaccines_due_list:
        for disease in client.vaccines_due_list:
            label = display_label(
                "diseases_overdue", disease, client.language, strict=False
            )
            vaccines_due_array_translated.append(label)

    # Translate vaccines_due string
    vaccines_due_str_translated = (
        ", ".join(vaccines_due_array_translated)
        if vaccines_due_array_translated
        else ""
    )

    # Translate received records' diseases
    received_translated: List[Dict[str, object]] = []
    if client.received:
        for record in client.received:
            translated_record = dict(record)
            # Translate diseases field (not vaccine)
            if "diseases" in translated_record and isinstance(
                translated_record["diseases"], list
            ):
                translated_diseases = []
                for disease in translated_record["diseases"]:
                    label = display_label(
                        "diseases_chart", disease, client.language, strict=False
                    )
                    translated_diseases.append(label)
                translated_record["diseases"] = translated_diseases
            received_translated.append(translated_record)

    return {
        "client_row": to_typ_value([client.client_id]),
        "client_data": to_typ_value(client_data),
        "vaccines_due_str": to_typ_value(vaccines_due_str_translated),
        "vaccines_due_array": to_typ_value(vaccines_due_array_translated),
        "received": to_typ_value(received_translated),
        "num_rows": str(len(received_translated)),
    }


def to_root_relative(path: Path) -> str:
    """Convert absolute path to project-root-relative Typst path reference.

    Module-internal helper for template rendering. Converts absolute file paths
    to paths relative to the project root, formatted for Typst's import resolution.
    Required because Typst subprocess needs paths resolvable from the project directory.

    Parameters
    ----------
    path : Path
        Absolute path to convert.

    Returns
    -------
    str
        Path string like "/artifacts/qr_codes/code.png" (relative to project root).

    Raises
    ------
    ValueError
        If path is outside the project root.
    """
    absolute = path.resolve()
    try:
        relative = absolute.relative_to(ROOT_DIR)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"Path {absolute} is outside of project root {ROOT_DIR}"
        ) from exc
    return "/" + relative.as_posix()


def render_notice(
    client: ClientRecord,
    *,
    output_dir: Path,
    logo: Path,
    signature: Path,
    parameters: Path,
    qr_output_dir: Path | None = None,
) -> str:
    language = Language.from_string(client.language)
    renderer = get_language_renderer(language)
    context = build_template_context(client, qr_output_dir)
    return renderer(
        context,
        logo_path=to_root_relative(logo),
        signature_path=to_root_relative(signature),
        parameters_path=to_root_relative(parameters),
    )


def generate_typst_files(
    payload: ArtifactPayload,
    output_dir: Path,
    logo_path: Path,
    signature_path: Path,
    parameters_path: Path,
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    qr_output_dir = output_dir / "qr_codes"
    typst_output_dir = output_dir / "typst"
    typst_output_dir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    language = payload.language
    for client in payload.clients:
        if client.language != language:
            raise ValueError(
                f"Client {client.client_id} language {client.language!r} does not match artifact language {language!r}."
            )
        typst_content = render_notice(
            client,
            output_dir=output_dir,
            logo=logo_path,
            signature=signature_path,
            parameters=parameters_path,
            qr_output_dir=qr_output_dir,
        )
        filename = f"{language}_notice_{client.sequence}_{client.client_id}.typ"
        file_path = typst_output_dir / filename
        file_path.write_text(typst_content, encoding="utf-8")
        files.append(file_path)
        LOG.info("Wrote %s", file_path)
    return files


def main(
    artifact_path: Path,
    output_dir: Path,
    logo_path: Path,
    signature_path: Path,
    parameters_path: Path,
) -> List[Path]:
    """Main entry point for Typst notice generation.

    Parameters
    ----------
    artifact_path : Path
        Path to the preprocessed JSON artifact.
    output_dir : Path
        Directory to write Typst files.
    logo_path : Path
        Path to the logo image.
    signature_path : Path
        Path to the signature image.
    parameters_path : Path
        Path to the YAML parameters file.

    Returns
    -------
    List[Path]
        List of generated Typst file paths.
    """
    payload = read_artifact(artifact_path)
    generated = generate_typst_files(
        payload,
        output_dir,
        logo_path,
        signature_path,
        parameters_path,
    )
    print(
        f"Generated {len(generated)} Typst files in {output_dir} for language {payload.language}"
    )
    return generated


if __name__ == "__main__":
    raise RuntimeError(
        "generate_notices.py should not be invoked directly. "
        "Use orchestrator.py instead."
    )
