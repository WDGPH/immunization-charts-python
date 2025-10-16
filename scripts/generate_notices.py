"""Generate per-client Typst notices from the normalized preprocessing artifact.

This is Task 3 from the refactor plan. It replaces the legacy shell-based generator
with a Python implementation that consumes the JSON file emitted by
``preprocess.py``.
"""
from __future__ import annotations

import json
import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

try:  # Allow both package and script-style invocation
    from .generate_mock_template_en import render_notice as render_notice_en
    from .generate_mock_template_fr import render_notice as render_notice_fr
except ImportError:  # pragma: no cover - fallback for CLI execution
    from generate_mock_template_en import render_notice as render_notice_en
    from generate_mock_template_fr import render_notice as render_notice_fr

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LANGUAGE_RENDERERS = {
    "en": render_notice_en,
    "fr": render_notice_fr,
}


@dataclass(frozen=True)
class ClientRecord:
    sequence: str
    client_id: str
    language: str
    person: Dict[str, str]
    school: Dict[str, str]
    board: Dict[str, str]
    contact: Dict[str, str]
    vaccines_due: str
    vaccines_due_list: List[str]
    received: List[Dict[str, object]]
    metadata: Dict[str, object]


@dataclass(frozen=True)
class ArtifactPayload:
    run_id: str
    language: str
    clients: List[ClientRecord]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Typst notices from preprocessed JSON.")
    parser.add_argument("artifact_path", type=Path, help="Path to the preprocessed JSON artifact.")
    parser.add_argument("output_dir", type=Path, help="Directory to write Typst files.")
    parser.add_argument("language", choices=LANGUAGE_RENDERERS.keys(), help="Language code (en/fr).")
    parser.add_argument("logo_path", type=Path, help="Path to the logo image.")
    parser.add_argument("signature_path", type=Path, help="Path to the signature image.")
    parser.add_argument("parameters_path", type=Path, help="Path to the YAML parameters file.")
    return parser.parse_args()


def read_artifact(path: Path) -> ArtifactPayload:
    payload = json.loads(path.read_text(encoding="utf-8"))
    clients = [ClientRecord(**client) for client in payload["clients"]]
    return ArtifactPayload(run_id=payload["run_id"], language=payload["language"], clients=clients)


def _escape_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
    )


def _to_typ_value(value) -> str:
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


def build_template_context(client: ClientRecord) -> Dict[str, str]:
    client_data = {
        "name": client.person["full_name"],
        "address": client.contact["street"],
        "city": client.contact["city"],
        "postal_code": client.contact["postal_code"],
        "date_of_birth": client.person["date_of_birth_display"],
        "school": client.school["name"],
    }

    return {
        "client_row": _to_typ_value([client.client_id]),
        "client_data": _to_typ_value(client_data),
        "vaccines_due_str": _to_typ_value(client.vaccines_due),
        "vaccines_due_array": _to_typ_value(client.vaccines_due_list),
        "received": _to_typ_value(client.received),
        "num_rows": str(len(client.received)),
    }


def _to_root_relative(path: Path) -> str:
    absolute = path.resolve()
    try:
        relative = absolute.relative_to(ROOT_DIR)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Path {absolute} is outside of project root {ROOT_DIR}") from exc
    return "/" + relative.as_posix()


def render_notice(
    client: ClientRecord,
    *,
    output_dir: Path,
    logo: Path,
    signature: Path,
    parameters: Path,
) -> str:
    renderer = LANGUAGE_RENDERERS[client.language]
    context = build_template_context(client)
    return renderer(
        context,
        logo_path=_to_root_relative(logo),
        signature_path=_to_root_relative(signature),
        parameters_path=_to_root_relative(parameters),
    )


def yield_clients(clients: Iterable[ClientRecord], language: str) -> Iterable[ClientRecord]:
    for client in clients:
        if client.language != language:
            continue
        yield client


def generate_typst_files(
    payload: ArtifactPayload,
    output_dir: Path,
    logo_path: Path,
    signature_path: Path,
    parameters_path: Path,
    *,
    language: str,
) -> List[Path]:
    if payload.language != language:
        raise ValueError(
            f"Artifact language {payload.language!r} does not match requested language {language!r}."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for client in yield_clients(payload.clients, language):
        typst_content = render_notice(
            client,
            output_dir=output_dir,
            logo=logo_path,
            signature=signature_path,
            parameters=parameters_path,
        )
        filename = f"{language}_client_{client.sequence}_{client.client_id}.typ"
        file_path = output_dir / filename
        file_path.write_text(typst_content, encoding="utf-8")
        files.append(file_path)
        LOG.info("Wrote %s", file_path)
    return files


def main() -> None:
    args = parse_args()
    payload = read_artifact(args.artifact_path)

    generated = generate_typst_files(
        payload,
        args.output_dir,
        args.logo_path,
        args.signature_path,
        args.parameters_path,
        language=args.language,
    )
    print(f"Generated {len(generated)} Typst files in {args.output_dir}")


if __name__ == "__main__":
    main()
