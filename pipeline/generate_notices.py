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
- File paths exist (output_dir, logo_path, signature_path)

Functions with special validation notes:
- render_notice(): Calls Language.from_string() on client.language to convert
  string to enum; this adds a second validation layer (redundant but safe)
- get_language_renderer(): Assumes language enum is valid; no defensive check
  (language validated upstream via CLI choices + Language.from_string())
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from .config_loader import load_config
from .data_models import (
    ArtifactPayload,
    ClientRecord,
)
from .enums import Language
from .preprocess import format_iso_date_for_language
from .translation_helpers import display_label
from .utils import deserialize_client_record

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
        client = deserialize_client_record(client_dict)
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


def load_and_translate_chart_diseases(language: str) -> List[str]:
    """Load and translate the chart disease list from configuration.

    Loads chart_diseases_header from config/parameters.yaml and translates each
    disease name to the target language using the diseases_chart translation domain.
    This ensures chart column headers match the configured set of diseases and are
    properly localized.

    Parameters
    ----------
    language : str
        Language code (e.g., "en", "fr").

    Returns
    -------
    List[str]
        List of translated disease names in order.
    """
    config = load_config()
    chart_diseases_header = config.get("chart_diseases_header", [])

    translated_diseases: List[str] = []
    for disease in chart_diseases_header:
        label = display_label("diseases_chart", disease, language, strict=False)
        translated_diseases.append(label)

    return translated_diseases


def build_template_context(
    client: ClientRecord,
    qr_output_dir: Path | None = None,
    map_file: Path = ROOT_DIR / "config/map_school.json",
    required_keys: Dict = {"phu_address", "phu_phone", "phu_email", "phu_website"},
) -> Dict[str, str]:
    """Build template context from client data.

    Translates disease names in vaccines_due_list and received records to
    localized display strings using the configured translation files.
    Also loads and translates the chart disease header list from configuration.
    Formats the notice date_data_cutoff with locale-aware formatting using Babel.

    Parameters
    ----------
    client : ClientRecord
        Client record with all required fields.
    qr_output_dir : Path, optional
        Directory containing QR code PNG files.
    map_file: Filepath, optional
        File containing mapping of schools to specific info (e.g. satellite PHU office info) to populate template.
        By default, will use config/map_school.json.
    required_keys: Dict, optional
        Dictionary containing the keys that should come from the mapping file.
        Each of these keys should be present in the "DEFAULT" section of the mapping file.
    Returns
    -------
    Dict[str, str]
        Template context with translated disease names and formatted date.
    """
    config = load_config()

    # Load and format date_data_cutoff for the client's language
    date_data_cutoff_iso = config.get("date_data_cutoff")
    if date_data_cutoff_iso:
        date_data_cutoff_formatted = format_iso_date_for_language(
            date_data_cutoff_iso, client.language
        )
    else:
        date_data_cutoff_formatted = ""

    client_data = {
        "name": " ".join(
            filter(None, [client.person["first_name"], client.person["last_name"]])
        ).strip(),
        "address": client.contact["street"],
        "city": client.contact["city"],
        "postal_code": client.contact["postal_code"],
        "date_of_birth": client.person["date_of_birth_display"],
        "school": client.school["name"],
        "date_data_cutoff": date_data_cutoff_formatted,
    }

    # Check if QR code PNG exists from prior generation step
    if qr_output_dir:
        qr_filename = f"qr_code_{client.sequence}_{client.client_id}.png"
        qr_path = qr_output_dir / qr_filename
        if qr_path.exists():
            client_data["qr_code"] = to_root_relative(qr_path)

    # Check if mapping file exists
    if not map_file.exists():
        raise FileNotFoundError(
            f"Expected school mapping file at {map_file}, but file does not exist. Please provide mapping file at {map_file}."
        )

    # Load mapping file data
    with open(map_file, "r") as f:
        map_data = json.load(f)

    # Attempt to load default PHU data values from mapping file; this should also contain all required keys
    try:
        phu_data = map_data["DEFAULT"]
    except KeyError as err:
        raise (
            f"Loading default PHU info, error when attempting to access 'DEFAULT' from {map_file}: {err}"
        )

    if not phu_data:
        raise ValueError(
            "Default values for PHU info not provided. "
            f'Please define DEFAULT values {required_keys} in under "DEFAULT" key in {map_file}.'
        )
    else:
        missing = [key for key in required_keys if key not in phu_data]
        if missing:
            missing_keys = ", ".join(missing)
            raise KeyError(f"Missing phu_data keys in config: {missing_keys}")

    # Clean school name
    client_school_key = re.sub(r"\s+", "_", client_data["school"]).upper()

    # Check if school has a mapping associated with it - otherwise, use default config values
    if client_school_key in map_data.keys():
        if client_school_key != "DEFAULT":
            LOG.info(f"School-specific information provided for: {client_school_key}")

            map_client_data = map_data[client_school_key]

            # Replace default values with values in map file. If any are missing, keep default values.
            for key in phu_data.keys():
                if key in map_client_data.keys():
                    phu_data[key] = map_client_data[key]
                else:
                    LOG.info(
                        f"Mapping file for school {client_school_key} missing {key}. Using default value."
                    )

    else:
        LOG.info(
            f"School {client_school_key} not in mapping file. Using default values."
        )

    # Load and translate chart disease header
    chart_diseases_translated = load_and_translate_chart_diseases(client.language)

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
        "phu_data": phu_data,
        "vaccines_due_str": to_typ_value(vaccines_due_str_translated),
        "vaccines_due_array": to_typ_value(vaccines_due_array_translated),
        "received": to_typ_value(received_translated),
        "num_rows": str(len(received_translated)),
        "chart_diseases_translated": to_typ_value(chart_diseases_translated),
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
    qr_output_dir: Path | None = None,
) -> str:
    language = Language.from_string(client.language)
    renderer = get_language_renderer(language)
    context = build_template_context(client, qr_output_dir)
    return renderer(
        context,
        logo_path=to_root_relative(logo),
        signature_path=to_root_relative(signature),
    )


def generate_typst_files(
    payload: ArtifactPayload, output_dir: Path, logo_path: Path, signature_path: Path
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
            qr_output_dir=qr_output_dir,
        )
        filename = f"{language}_notice_{client.sequence}_{client.client_id}.typ"
        file_path = typst_output_dir / filename
        file_path.write_text(typst_content, encoding="utf-8")
        files.append(file_path)
        LOG.info("Wrote %s", file_path)
    return files


def main(
    artifact_path: Path, output_dir: Path, logo_path: Path, signature_path: Path
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

    Returns
    -------
    List[Path]
        List of generated Typst file paths.
    """
    payload = read_artifact(artifact_path)
    generated = generate_typst_files(payload, output_dir, logo_path, signature_path)
    print(
        f"Generated {len(generated)} Typst files in {output_dir} for language {payload.language}"
    )
    return generated


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
