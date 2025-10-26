"""Generate QR code PNG files from preprocessed client artifact.

This module creates QR code images for each client in the preprocessed artifact.
QR payloads are generated from template strings defined in parameters.yaml and
rendered as PNG files in the output artifacts directory.

The QR code generation step is optional and can be skipped via the qr.enabled
configuration setting.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from string import Formatter
from typing import Any, Dict, List, Optional

import yaml

try:
    import qrcode
    from qrcode import constants as qrcode_constants
    from PIL import Image
except ImportError:
    qrcode = None  # type: ignore
    qrcode_constants = None  # type: ignore
    Image = None  # type: ignore

from .config_loader import load_config

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
CONFIG_DIR = ROOT_DIR / "config"
PARAMETERS_PATH = CONFIG_DIR / "parameters.yaml"

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SUPPORTED_QR_TEMPLATE_FIELDS = {
    "client_id",
    "first_name",
    "last_name",
    "name",
    "date_of_birth",
    "date_of_birth_iso",
    "school",
    "city",
    "postal_code",
    "province",
    "street_address",
    "language_code",
    "delivery_date",
}

_FORMATTER = Formatter()


def generate_qr_code(
    data: str,
    output_dir: Path,
    *,
    filename: Optional[str] = None,
) -> Path:
    """Generate a monochrome QR code PNG and return the saved path.

    Parameters
    ----------
    data:
        The string payload to encode inside the QR code.
    output_dir:
        Directory where the QR image should be saved. The directory is created
        if it does not already exist.
    filename:
        Optional file name (including extension) for the resulting PNG. When
        omitted a deterministic name derived from the payload hash is used.

    Returns
    -------
    Path
        Absolute path to the generated PNG file.
    """

    if qrcode is None or Image is None:  # pragma: no cover - exercised in optional envs
        raise RuntimeError(
            "QR code generation requires the 'qrcode' and 'pillow' packages. "
            "Install them via 'uv sync' before enabling QR payloads."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode_constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    pil_image = getattr(image, "get_image", lambda: image)()

    # Convert to 1-bit black/white without dithering to keep crisp edges.
    # NONE (0) means no dithering
    pil_bitmap = pil_image.convert("1", dither=0)

    if not filename:
        digest = hashlib.sha1(data.encode("utf-8")).hexdigest()[:12]
        filename = f"qr_{digest}.png"

    target_path = output_dir / filename
    pil_bitmap.save(target_path, format="PNG", bits=1)
    return target_path


def read_preprocessed_artifact(path: Path) -> Dict[str, Any]:
    """Read preprocessed client artifact from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _string_or_empty(value: Any) -> str:
    """Safely convert value to string, returning empty string for None/NaN."""
    if value is None:
        return ""
    return str(value).strip()


def _extract_template_fields(template: str) -> set[str]:
    """Extract placeholder names from a format string."""
    try:
        return {
            field_name
            for _, field_name, _, _ in _FORMATTER.parse(template)
            if field_name
        }
    except ValueError as exc:
        raise ValueError(f"Invalid QR payload template: {exc}") from exc


def _format_qr_payload(template: str, context: Dict[str, str]) -> str:
    """Format and validate QR payload template against allowed placeholders.

    Validates that all placeholders in the template exist in the provided context
    and are part of SUPPORTED_QR_TEMPLATE_FIELDS. Raises ValueError if unsupported
    placeholders are used.
    """
    placeholders = _extract_template_fields(template)
    unknown_fields = placeholders - context.keys()
    if unknown_fields:
        raise KeyError(
            f"Unknown placeholder(s) {sorted(unknown_fields)} in qr_payload_template. "
            f"Available placeholders: {sorted(context.keys())}"
        )

    disallowed = placeholders - SUPPORTED_QR_TEMPLATE_FIELDS
    if disallowed:
        raise ValueError(
            f"Disallowed placeholder(s) {sorted(disallowed)} in qr_payload_template. "
            f"Allowed placeholders: {sorted(SUPPORTED_QR_TEMPLATE_FIELDS)}"
        )

    return template.format(**context)


def _build_qr_context(
    *,
    client_id: str,
    first_name: str,
    last_name: str,
    dob_display: str,
    dob_iso: Optional[str],
    school: str,
    city: str,
    postal_code: str,
    province: str,
    street_address: str,
    language_code: str,
    delivery_date: Optional[str],
) -> Dict[str, str]:
    """Build template context for QR payload formatting."""
    return {
        "client_id": _string_or_empty(client_id),
        "first_name": _string_or_empty(first_name),
        "last_name": _string_or_empty(last_name),
        "name": " ".join(
            filter(
                None,
                [_string_or_empty(first_name), _string_or_empty(last_name)],
            )
        ).strip(),
        "date_of_birth": _string_or_empty(dob_display),
        "date_of_birth_iso": _string_or_empty(dob_iso),
        "school": _string_or_empty(school),
        "city": _string_or_empty(city),
        "postal_code": _string_or_empty(postal_code),
        "province": _string_or_empty(province),
        "street_address": _string_or_empty(street_address),
        "language_code": _string_or_empty(language_code),  # ISO code: 'en' or 'fr'
        "delivery_date": _string_or_empty(delivery_date),
    }


def load_qr_settings(config_path: Path | None = None) -> tuple[str, Optional[str]]:
    """Load QR configuration from parameters.yaml file.

    Raises ValueError if qr.payload_template is not specified in the configuration.

    Returns:
        Tuple of (payload_template, delivery_date)
    """
    if config_path is None:
        config_path = PARAMETERS_PATH

    if not config_path.exists():
        raise FileNotFoundError(
            f"QR code generation enabled but configuration file not found: {config_path}"
        )

    params = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config_data = params.get("qr", {})

    template_config = config_data.get("payload_template")
    if not template_config:
        raise ValueError(
            "QR code generation is enabled but qr.payload_template is not specified in config. "
            "Please define qr.payload_template in parameters.yaml or set qr.enabled to false."
        )

    if not isinstance(template_config, str):
        raise ValueError(
            f"qr.payload_template must be a string, got {type(template_config).__name__}"
        )

    payload_template = template_config
    delivery_date = params.get("delivery_date")

    return payload_template, delivery_date


def generate_qr_codes(
    artifact_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
) -> List[Path]:
    """Generate QR code PNG files from preprocessed artifact.

    Parameters
    ----------
    artifact_path : Path
        Path to the preprocessed JSON artifact.
    output_dir : Path
        Directory to write QR code PNG files.
    config_path : Path, optional
        Path to parameters.yaml. If not provided, uses default location.

    Returns
    -------
    List[Path]
        List of generated QR code PNG file paths.
    """
    if config_path is None:
        config_path = PARAMETERS_PATH

    # Load QR configuration
    config = load_config(config_path)
    qr_config = config.get("qr", {})
    qr_enabled = qr_config.get("enabled", True)

    if not qr_enabled:
        LOG.info("QR code generation disabled in configuration")
        return []

    # Read artifact
    artifact = read_preprocessed_artifact(artifact_path)
    language = artifact.get("language", "en")
    clients = artifact.get("clients", [])

    if not clients:
        LOG.info("No clients in artifact")
        return []

    # Load QR settings (will raise ValueError if template not specified)
    try:
        payload_template, delivery_date = load_qr_settings(config_path)
    except (FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"Cannot generate QR codes: {exc}") from exc

    # Ensure output directory exists
    qr_output_dir = output_dir / "qr_codes"
    qr_output_dir.mkdir(parents=True, exist_ok=True)

    generated_files: List[Path] = []

    # Generate QR code for each client
    for client in clients:
        client_id = client.get("client_id")
        sequence = client.get("sequence")

        # Get client details for context
        person = client.get("person", {})
        contact = client.get("contact", {})
        school = client.get("school", {})

        # Build QR context
        qr_context = _build_qr_context(
            client_id=client_id,
            first_name=person.get("first_name", ""),
            last_name=person.get("last_name", ""),
            dob_display=person.get("date_of_birth_display", ""),
            dob_iso=person.get("date_of_birth_iso"),
            school=school.get("name", ""),
            city=contact.get("city", ""),
            postal_code=contact.get("postal_code", ""),
            province=contact.get("province", ""),
            street_address=contact.get("street", ""),
            language_code=language,
            delivery_date=delivery_date,
        )

        # Generate payload (template is now required)
        try:
            qr_payload = _format_qr_payload(payload_template, qr_context)
        except (KeyError, ValueError) as exc:
            LOG.warning(
                "Could not format QR payload for client %s: %s",
                client_id,
                exc,
            )
            continue

        # Generate PNG
        try:
            qr_path = generate_qr_code(
                qr_payload,
                qr_output_dir,
                filename=f"qr_code_{sequence}_{client_id}.png",
            )
            generated_files.append(qr_path)
            LOG.info("Generated QR code for client %s: %s", client_id, qr_path)
        except RuntimeError as exc:
            LOG.warning(
                "Could not generate QR code for client %s: %s",
                client_id,
                exc,
            )

    return generated_files


def main(
    artifact_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
) -> int:
    """Main entry point for QR code generation.

    Parameters
    ----------
    artifact_path : Path
        Path to the preprocessed JSON artifact.
    output_dir : Path
        Directory to write QR code PNG files.
    config_path : Path, optional
        Path to parameters.yaml configuration file.

    Returns
    -------
    int
        Number of QR codes generated.
    """
    generated = generate_qr_codes(artifact_path, output_dir, config_path)
    if generated:
        print(
            f"Generated {len(generated)} QR code PNG file(s) in {output_dir}/qr_codes/"
        )
    return len(generated)


if __name__ == "__main__":
    raise RuntimeError(
        "generate_qr_codes.py should not be invoked directly. "
        "Use orchestrator.py instead."
    )
