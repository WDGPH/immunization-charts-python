"""Generate per-client Typst notices from the normalized preprocessing artifact.

This module consumes the JSON artifact emitted by ``preprocess.py`` and generates
per-client Typst templates for notice rendering.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import typst

from .data_models import (
    ArtifactPayload,
    ClientRecord,
)

from templates.en_template import render_notice as render_notice_en
from templates.fr_template import render_notice as render_notice_fr

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Colocated from utils.py
def compile_typst(immunization_record, outpath):
    """Compile a Typst template to PDF output.

    Parameters
    ----------
    immunization_record : str
        Path to the Typst template file.
    outpath : str
        Path to output PDF file.
    """
    typst.compile(immunization_record, output=outpath)


LANGUAGE_RENDERERS = {
    "en": render_notice_en,
    "fr": render_notice_fr,
}


def read_artifact(path: Path) -> ArtifactPayload:
    """Read and deserialize the preprocessed artifact JSON.

    Parameters
    ----------
    path : Path
        Path to the preprocessed artifact JSON file.

    Returns
    -------
    ArtifactPayload
        Parsed artifact with clients and metadata.
    """
    payload_dict = json.loads(path.read_text(encoding="utf-8"))
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


def _escape_string(value: str) -> str:
    """Escape special characters in a string for Typst template output.

    Escapes backslashes, quotes, and newlines to ensure the string can be
    safely embedded in a Typst template.

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


def _to_typ_value(value) -> str:
    """Convert a Python value to its Typst template representation.

    Handles strings (with escaping), booleans, None, numbers, sequences (tuples),
    and mappings (dicts) by converting them to Typst syntax.

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
    >>> _to_typ_value("hello")
    '"hello"'
    >>> _to_typ_value(True)
    'true'
    >>> _to_typ_value([1, 2, 3])
    '(1, 2, 3)'
    """
    if isinstance(value, str):
        return f'"{_escape_string(value)}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [_to_typ_value(item) for item in value]
        if len(items) == 1:
            inner = f"{items[0]},"
        else:
            inner = ", ".join(items)
        return f"({inner})"
    if isinstance(value, Mapping):
        items = ", ".join(f"{key}: {_to_typ_value(val)}" for key, val in value.items())
        return f"({items})"
    raise TypeError(f"Unsupported value type for Typst conversion: {type(value)!r}")


def build_template_context(
    client: ClientRecord, qr_output_dir: Path | None = None
) -> Dict[str, str]:
    """Build template context from client data."""
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
            client_data["qr_code"] = _to_root_relative(qr_path)

    return {
        "client_row": _to_typ_value([client.client_id]),
        "client_data": _to_typ_value(client_data),
        "vaccines_due_str": _to_typ_value(client.vaccines_due or ""),
        "vaccines_due_array": _to_typ_value(client.vaccines_due_list or []),
        "received": _to_typ_value(client.received or []),
        "num_rows": str(len(client.received or [])),
    }


def _to_root_relative(path: Path) -> str:
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
    renderer = LANGUAGE_RENDERERS[client.language]
    context = build_template_context(client, qr_output_dir)
    return renderer(
        context,
        logo_path=_to_root_relative(logo),
        signature_path=_to_root_relative(signature),
        parameters_path=_to_root_relative(parameters),
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
