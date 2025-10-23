"""Preprocessing pipeline for immunization-charts.

Normalizes and structures input data into a single JSON artifact for downstream
pipeline steps. Handles data validation, client sorting, vaccine processing, and
optional QR payload formatting.

Supported Template Placeholders
--------------------------------
The following placeholders are supported in QR payload_template and encryption
password_template configurations. Attempting to use any other placeholder will
raise a ValueError at runtime.

QR Payload Template Placeholders:
    - client_id: Client identifier
    - first_name: Client first name
    - last_name: Client last name
    - name: Combined first and last name
    - date_of_birth: Formatted date (e.g., "May 8, 2025")
    - date_of_birth_iso: ISO format date (e.g., "2025-05-08")
    - school: School name
    - city: City
    - postal_code: Postal code
    - province: Province/territory
    - street_address: Street address
    - language: Language label (e.g., "english", "french")
    - language_code: Language code (e.g., "en", "fr")
    - delivery_date: Delivery date

Encryption Password Template Placeholders:
    - client_id: Client identifier
    - first_name: Client first name
    - last_name: Client last name
    - name: Combined first and last name
    - date_of_birth: Formatted date
    - date_of_birth_iso: ISO format date (e.g., "2025-05-08")
    - date_of_birth_iso_compact: Compact ISO format (e.g., "20250508")
    - school: School name
    - city: City
    - postal_code: Postal code
    - province: Province/territory
    - street_address: Street address
    - language: Language label
    - language_code: Language code
    - delivery_date: Delivery date
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from string import Formatter
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import yaml

from .utils import (
    convert_date_iso,
    convert_date_string,
    convert_date_string_french,
    over_16_check,
)

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
DISEASE_MAP_PATH = CONFIG_DIR / "disease_map.json"
VACCINE_REFERENCE_PATH = CONFIG_DIR / "vaccine_reference.json"
PARAMETERS_PATH = CONFIG_DIR / "parameters.yaml"

LOG = logging.getLogger(__name__)

LANGUAGE_LABELS = {
    "en": "english",
    "fr": "french",
}

SUPPORTED_QR_TEMPLATE_FIELDS: Set[str] = {
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
    "language",
    "language_code",
    "delivery_date",
}

DEFAULT_QR_PAYLOAD_TEMPLATE = {
    "en": "https://www.test-immunization.ca/update?client_id={client_id}&dob={date_of_birth_iso}",
    "fr": "https://www.test-immunization.ca/update?client_id={client_id}&dob={date_of_birth_iso}",
}

_FORMATTER = Formatter()

IGNORE_AGENTS = [
    "-unspecified",
    "unspecified",
    "Not Specified",
    "Not specified",
    "Not Specified-unspecified",
]

REQUIRED_COLUMNS = [
    "SCHOOL NAME",
    "CLIENT ID",
    "FIRST NAME",
    "LAST NAME",
    "DATE OF BIRTH",
    "CITY",
    "POSTAL CODE",
    "PROVINCE/TERRITORY",
    "OVERDUE DISEASE",
    "IMMS GIVEN",
    "STREET ADDRESS LINE 1",
    "STREET ADDRESS LINE 2",
]


@dataclass
class PreprocessResult:
    clients: List[Dict[str, Any]]
    warnings: List[str]
    qr: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class QrSettings:
    payload_template: Optional[str]
    delivery_date: Optional[str]


def configure_logging(output_dir: Path, run_id: str) -> Path:
    """Configure file logging for preprocessing step."""
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"preprocess_{run_id}.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    return log_path


def detect_file_type(file_path: Path) -> str:
    """Return the file extension for preprocessing logic."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    return file_path.suffix.lower()


def read_input(file_path: Path) -> pd.DataFrame:
    """Read CSV/Excel into DataFrame with robust encoding and delimiter detection."""
    ext = detect_file_type(file_path)

    try:
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, engine="openpyxl")
        elif ext == ".csv":
            # Try common encodings
            for enc in ["utf-8-sig", "latin-1", "cp1252"]:
                try:
                    # Let pandas sniff the delimiter
                    df = pd.read_csv(file_path, sep=None, encoding=enc, engine="python")
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                raise ValueError(
                    "Could not decode CSV with common encodings or delimiters"
                )
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        LOG.info("Loaded %s rows from %s", len(df), file_path)
        return df

    except Exception as exc:  # pragma: no cover - logging branch
        LOG.error("Failed to read %s: %s", file_path, exc)
        raise


def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names and validate required columns."""
    df = df.copy()
    df.columns = [col.strip().upper() for col in df.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df.rename(columns=lambda x: x.replace(" ", "_"), inplace=True)
    df.rename(columns={"PROVINCE/TERRITORY": "PROVINCE"}, inplace=True)
    return df


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize data types and fill missing values."""
    working = df.copy()
    string_columns = [
        "SCHOOL_NAME",
        "FIRST_NAME",
        "LAST_NAME",
        "CITY",
        "PROVINCE",
        "POSTAL_CODE",
        "STREET_ADDRESS_LINE_1",
        "STREET_ADDRESS_LINE_2",
        "SCHOOL_TYPE",
        "BOARD_NAME",
        "BOARD_ID",
        "SCHOOL_ID",
        "UNIQUE_ID",
    ]

    for column in string_columns:
        if column not in working.columns:
            working[column] = ""
        working[column] = working[column].fillna(" ").astype(str).str.strip()

    working["DATE_OF_BIRTH"] = pd.to_datetime(working["DATE_OF_BIRTH"], errors="coerce")
    if "AGE" in working.columns:
        working["AGE"] = pd.to_numeric(working["AGE"], errors="coerce")
    else:
        working["AGE"] = pd.NA

    if "BOARD_NAME" not in working.columns:
        working["BOARD_NAME"] = ""
    if "BOARD_ID" not in working.columns:
        working["BOARD_ID"] = ""
    if "SCHOOL_TYPE" not in working.columns:
        working["SCHOOL_TYPE"] = ""

    return working


def synthesize_identifier(existing: str, source: str, prefix: str) -> str:
    """Generate a deterministic identifier if one is not provided."""
    existing = (existing or "").strip()
    if existing:
        return existing

    base = (source or "").strip().lower() or "unknown"
    digest = sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def process_vaccines_due(
    vaccines_due: Any, language: str, disease_map: Dict[str, str]
) -> str:
    """Map overdue diseases to vaccine names using disease_map."""
    if not isinstance(vaccines_due, str) or not vaccines_due.strip():
        return ""

    replacements = {
        "en": {
            "Haemophilus influenzae infection, invasive": "Invasive Haemophilus influenzae infection (Hib)",
        },
        "fr": {
            "infection à Haemophilus influenzae, invasive": "Haemophilus influenzae de type b (Hib)",
        },
    }

    normalised = vaccines_due
    for original, replacement in replacements.get(language, {}).items():
        normalised = normalised.replace(original, replacement)

    items: List[str] = []
    for token in normalised.split(","):
        cleaned = token.strip()
        mapped = disease_map.get(cleaned, cleaned)
        items.append(mapped)

    return ", ".join(item.replace("'", "").replace('"', "") for item in items if item)


def process_received_agents(
    received_agents: Any, ignore_agents: List[str]
) -> List[Dict[str, Any]]:
    """Extract and normalize vaccination history from received_agents string."""
    if not isinstance(received_agents, str) or not received_agents.strip():
        return []

    pattern = re.compile(r"\w{3} \d{1,2}, \d{4} - [^,]+")
    matches = pattern.findall(received_agents)
    rows: List[Dict[str, Any]] = []

    for match in matches:
        date_str, vaccine = match.split(" - ", maxsplit=1)
        vaccine = vaccine.strip()
        if vaccine in ignore_agents:
            continue
        date_iso = convert_date_iso(date_str.strip())
        rows.append({"date_given": date_iso, "vaccine": vaccine})

    rows.sort(key=lambda item: item["date_given"])
    grouped: List[Dict[str, Any]] = []
    for entry in rows:
        if not grouped or grouped[-1]["date_given"] != entry["date_given"]:
            grouped.append(
                {
                    "date_given": entry["date_given"],
                    "vaccine": [entry["vaccine"]],
                }
            )
        else:
            grouped[-1]["vaccine"].append(entry["vaccine"])

    return grouped


def enrich_grouped_records(
    grouped: List[Dict[str, Any]],
    vaccine_reference: Dict[str, Any],
    language: str,
) -> List[Dict[str, Any]]:
    """Enrich grouped vaccine records with disease information."""
    enriched: List[Dict[str, Any]] = []
    for item in grouped:
        vaccines = [
            v.replace("-unspecified", "*").replace(" unspecified", "*")
            for v in item["vaccine"]
        ]
        diseases: List[str] = []
        for vaccine in vaccines:
            ref = vaccine_reference.get(vaccine, vaccine)
            if isinstance(ref, list):
                diseases.extend(ref)
            else:
                diseases.append(ref)
        enriched.append(
            {
                "date_given": item["date_given"],
                "vaccine": vaccines,
                "diseases": diseases,
            }
        )
    return enriched


def _string_or_empty(value: Any) -> str:
    """Safely convert value to string, returning empty string for None/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _extract_template_fields(template: str) -> Set[str]:
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


def _default_qr_payload(context: Dict[str, str]) -> str:
    """Generate default QR payload as JSON."""
    payload = {
        "id": context.get("client_id"),
        "name": context.get("name"),
        "dob": context.get("date_of_birth_iso"),
        "school": context.get("school"),
    }
    return json.dumps(payload, sort_keys=True)


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
    language_label = LANGUAGE_LABELS.get(language_code, language_code)
    return {
        "client_id": _string_or_empty(client_id),
        "first_name": _string_or_empty(first_name),
        "last_name": _string_or_empty(last_name),
        "name": " ".join(
            filter(None, [_string_or_empty(first_name), _string_or_empty(last_name)])
        ).strip(),
        "date_of_birth": _string_or_empty(dob_display),
        "date_of_birth_iso": _string_or_empty(dob_iso),
        "school": _string_or_empty(school),
        "city": _string_or_empty(city),
        "postal_code": _string_or_empty(postal_code),
        "province": _string_or_empty(province),
        "street_address": _string_or_empty(street_address),
        "language": language_label,
        "language_code": _string_or_empty(language_code),
        "delivery_date": _string_or_empty(delivery_date),
    }


def load_qr_settings(language: str, *, config_path: Path = None) -> QrSettings:
    """Load QR configuration from parameters.yaml file.

    Reads the QR configuration section from the unified parameters.yaml file.
    If config_path is not provided, uses the default PARAMETERS_PATH.

    Supported placeholders for payload_template are defined in SUPPORTED_QR_TEMPLATE_FIELDS.
    Attempts to use any other placeholder will raise a ValueError during validation.
    """
    if config_path is None:
        config_path = PARAMETERS_PATH

    payload_template = DEFAULT_QR_PAYLOAD_TEMPLATE.get(language)
    delivery_date: Optional[str] = None

    if not config_path.exists():
        LOG.info("Parameters file not found at %s; using defaults.", config_path)
        return QrSettings(payload_template, delivery_date)

    params = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config_data = params.get("qr", {})

    template_config = config_data.get("payload_template")
    if isinstance(template_config, dict):
        for key in (language, LANGUAGE_LABELS.get(language)):
            if key and template_config.get(key):
                payload_template = template_config[key]
                break
    elif isinstance(template_config, str):
        payload_template = template_config
    elif template_config is not None:
        LOG.warning(
            "Ignoring qr.payload_template with unsupported type %s; expected str or mapping.",
            type(template_config).__name__,
        )

    delivery_date = config_data.get("delivery_date") or delivery_date

    return QrSettings(payload_template, delivery_date)


def build_preprocess_result(
    df: pd.DataFrame,
    language: str,
    disease_map: Dict[str, str],
    vaccine_reference: Dict[str, Any],
    ignore_agents: List[str],
    qr_settings: Optional[QrSettings] = None,
) -> PreprocessResult:
    """Process and normalize client data into structured artifact."""
    qr_settings = qr_settings or load_qr_settings(language)
    warnings: set[str] = set()
    working = normalize_dataframe(df)

    working["SCHOOL_ID"] = working.apply(
        lambda row: synthesize_identifier(
            row.get("SCHOOL_ID", ""), row["SCHOOL_NAME"], "sch"
        ),
        axis=1,
    )
    working["BOARD_ID"] = working.apply(
        lambda row: synthesize_identifier(
            row.get("BOARD_ID", ""), row.get("BOARD_NAME", ""), "brd"
        ),
        axis=1,
    )

    if (working["BOARD_NAME"] == "").any():
        affected = (
            working.loc[working["BOARD_NAME"] == "", "SCHOOL_NAME"].unique().tolist()
        )
        warnings.add(
            "Missing board name for: " + ", ".join(sorted(filter(None, affected)))
            if affected
            else "Missing board name for one or more schools."
        )

    sorted_df = working.sort_values(
        by=["SCHOOL_NAME", "LAST_NAME", "FIRST_NAME", "CLIENT_ID"],
        kind="stable",
    ).reset_index(drop=True)
    sorted_df["SEQUENCE"] = [f"{idx + 1:05d}" for idx in range(len(sorted_df))]

    clients: List[Dict[str, Any]] = []
    for row in sorted_df.itertuples(index=False):
        client_id = str(row.CLIENT_ID)
        sequence = row.SEQUENCE
        dob_iso = (
            row.DATE_OF_BIRTH.strftime("%Y-%m-%d")
            if pd.notna(row.DATE_OF_BIRTH)
            else None
        )
        if dob_iso is None:
            warnings.add(f"Missing date of birth for client {client_id}")

        formatted_dob = (
            convert_date_string_french(dob_iso)
            if language == "fr" and dob_iso
            else convert_date_string(dob_iso)
        )
        vaccines_due = process_vaccines_due(row.OVERDUE_DISEASE, language, disease_map)
        vaccines_due_list = [
            item.strip() for item in vaccines_due.split(",") if item.strip()
        ]
        received_grouped = process_received_agents(row.IMMS_GIVEN, ignore_agents)
        received = enrich_grouped_records(received_grouped, vaccine_reference, language)

        postal_code = row.POSTAL_CODE if row.POSTAL_CODE else "Not provided"
        address_line = " ".join(
            filter(None, [row.STREET_ADDRESS_LINE_1, row.STREET_ADDRESS_LINE_2])
        ).strip()

        if not pd.isna(row.AGE):
            over_16 = bool(row.AGE >= 16)
        elif dob_iso and qr_settings.delivery_date:
            over_16 = over_16_check(dob_iso, qr_settings.delivery_date)
        else:
            over_16 = False

        client_entry = {
            "sequence": sequence,
            "client_id": client_id,
            "language": language,
            "school": {
                "id": row.SCHOOL_ID,
                "name": row.SCHOOL_NAME,
                "type": row.SCHOOL_TYPE or None,
            },
            "board": {
                "id": row.BOARD_ID,
                "name": row.BOARD_NAME or None,
            },
            "person": {
                "first_name": row.FIRST_NAME,
                "last_name": row.LAST_NAME,
                "full_name": " ".join(
                    filter(None, [row.FIRST_NAME, row.LAST_NAME])
                ).strip(),
                "date_of_birth_iso": dob_iso,
                "date_of_birth_display": formatted_dob,
                "age": None if pd.isna(row.AGE) else int(row.AGE),
                "over_16": over_16,
            },
            "contact": {
                "street": address_line,
                "city": row.CITY,
                "province": row.PROVINCE,
                "postal_code": postal_code,
            },
            "vaccines_due": vaccines_due,
            "vaccines_due_list": vaccines_due_list,
            "received": received,
            "metadata": {
                "unique_id": row.UNIQUE_ID or None,
                "delivery_date": qr_settings.delivery_date,
            },
        }

        qr_context = _build_qr_context(
            client_id=client_id,
            first_name=row.FIRST_NAME,
            last_name=row.LAST_NAME,
            dob_display=formatted_dob or "",
            dob_iso=dob_iso,
            school=row.SCHOOL_NAME,
            city=row.CITY,
            postal_code=postal_code,
            province=row.PROVINCE,
            street_address=address_line,
            language_code=language,
            delivery_date=qr_settings.delivery_date,
        )

        qr_payload = _default_qr_payload(qr_context)
        if qr_settings.payload_template:
            try:
                qr_payload = _format_qr_payload(
                    qr_settings.payload_template,
                    qr_context,
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Failed to format QR payload for client {client_id}: {exc}"
                ) from exc

        client_entry["qr"] = {
            "payload": qr_payload,
        }

        clients.append(client_entry)

    qr_summary = {
        "payload_template": qr_settings.payload_template,
        "delivery_date": qr_settings.delivery_date,
    }

    return PreprocessResult(
        clients=clients,
        warnings=sorted(warnings),
        qr=qr_summary,
    )


def write_artifact(
    output_dir: Path, language: str, run_id: str, result: PreprocessResult
) -> Path:
    """Write preprocessed result to JSON artifact file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "language": language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_clients": len(result.clients),
        "clients": result.clients,
        "warnings": result.warnings,
    }
    if result.qr is not None:
        payload["qr"] = result.qr
    artifact_path = output_dir / f"preprocessed_clients_{run_id}.json"
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG.info("Wrote normalized artifact to %s", artifact_path)
    return artifact_path


def extract_total_clients(artifact_path: Path) -> int:
    """Extract total client count from preprocessed artifact."""
    with artifact_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    total: Optional[int] = payload.get("total_clients")
    if total is None:
        clients = payload.get("clients", [])
        total = len(clients)

    try:
        return int(total)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError("Unable to determine the total number of clients") from exc
