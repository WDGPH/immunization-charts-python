"""Preprocessing pipeline for immunization-charts.

Normalizes and structures input data into a single JSON artifact for downstream
pipeline steps. Handles data validation, client sorting, and vaccine processing.
QR code generation is handled by a separate step after preprocessing.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from string import Formatter
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from .data_models import (
    ArtifactPayload,
    ClientRecord,
    PreprocessResult,
)

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
DISEASE_MAP_PATH = CONFIG_DIR / "disease_map.json"
VACCINE_REFERENCE_PATH = CONFIG_DIR / "vaccine_reference.json"
PARAMETERS_PATH = CONFIG_DIR / "parameters.yaml"

LOG = logging.getLogger(__name__)

_FORMATTER = Formatter()

# Date conversion helpers (colocated from utils.py)
FRENCH_MONTHS = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}
FRENCH_MONTHS_REV = {v.lower(): k for k, v in FRENCH_MONTHS.items()}

ENGLISH_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
ENGLISH_MONTHS_REV = {v.lower(): k for k, v in ENGLISH_MONTHS.items()}


def convert_date_string_french(date_str):
    """Convert a date string from YYYY-MM-DD format to French display format.

    Parameters
    ----------
    date_str : str
        Date string in YYYY-MM-DD format.

    Returns
    -------
    str
        Date in French format (e.g., "8 mai 2025").
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day = date_obj.day
    month = FRENCH_MONTHS[date_obj.month]
    year = date_obj.year

    return f"{day} {month} {year}"


def convert_date_string(date_str):
    """Convert a date to English display format.

    Parameters
    ----------
    date_str : str | datetime | pd.Timestamp
        Date string in YYYY-MM-DD format or datetime-like object.

    Returns
    -------
    str
        Date in the format Mon DD, YYYY (e.g., "May 8, 2025").
    """
    if pd.isna(date_str):
        return None

    # If it's already a datetime or Timestamp
    if isinstance(date_str, (pd.Timestamp, datetime)):
        return date_str.strftime("%b %d, %Y")

    # Otherwise assume string input
    try:
        date_obj = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
        return date_obj.strftime("%b %d, %Y")
    except ValueError:
        raise ValueError(f"Unrecognized date format: {date_str}")


def convert_date_iso(date_str):
    """Convert a date from English display format to ISO format.

    Parameters
    ----------
    date_str : str
        Date in English display format (e.g., "May 8, 2025").

    Returns
    -------
    str
        Date in ISO format (YYYY-MM-DD).
    """
    date_obj = datetime.strptime(date_str, "%b %d, %Y")
    return date_obj.strftime("%Y-%m-%d")


def convert_date(
    date_str: str, to_format: str = "display", lang: str = "en"
) -> Optional[str]:
    """Convert dates between ISO and localized display formats.

    Parameters
    ----------
    date_str : str | datetime | pd.Timestamp
        Date string to convert.
    to_format : str, optional
        Target format - 'iso' or 'display' (default: 'display').
    lang : str, optional
        Language code 'en' or 'fr' (default: 'en').

    Returns
    -------
    str
        Formatted date string according to specified format.

    Examples
    --------
    convert_date('2025-05-08', 'display', 'en') -> 'May 8, 2025'
    convert_date('2025-05-08', 'display', 'fr') -> '8 mai 2025'
    convert_date('May 8, 2025', 'iso', 'en') -> '2025-05-08'
    convert_date('8 mai 2025', 'iso', 'fr') -> '2025-05-08'
    """
    if pd.isna(date_str):
        return None

    try:
        # Convert input to datetime object
        if isinstance(date_str, (pd.Timestamp, datetime)):
            date_obj = date_str
        elif isinstance(date_str, str):
            if "-" in date_str:  # ISO format
                date_obj = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            else:  # Localized format
                try:
                    if lang == "fr":
                        day, month, year = date_str.split()
                        month_num = FRENCH_MONTHS_REV.get(month.lower())
                        if not month_num:
                            raise ValueError(f"Invalid French month: {month}")
                        date_obj = datetime(int(year), month_num, int(day))
                    else:
                        month, rest = date_str.split(maxsplit=1)
                        day, year = rest.rstrip(",").split(",")
                        month_num = ENGLISH_MONTHS_REV.get(month.strip().lower())
                        if not month_num:
                            raise ValueError(f"Invalid English month: {month}")
                        date_obj = datetime(int(year), month_num, int(day.strip()))
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Unable to parse date string: {date_str}") from e
        else:
            raise ValueError(f"Unsupported date type: {type(date_str)}")

        # Convert to target format
        if to_format == "iso":
            return date_obj.strftime("%Y-%m-%d")
        else:  # display format
            if lang == "fr":
                month_name = FRENCH_MONTHS[date_obj.month]
                return f"{date_obj.day} {month_name} {date_obj.year}"
            else:
                month_name = ENGLISH_MONTHS[date_obj.month]
                return f"{month_name} {date_obj.day}, {date_obj.year}"

    except Exception as e:
        raise ValueError(f"Date conversion failed: {str(e)}") from e


def over_16_check(date_of_birth, delivery_date):
    """Check if a client is over 16 years old on delivery date.

    Parameters
    ----------
    date_of_birth : str
        Date of birth in YYYY-MM-DD format.
    delivery_date : str
        Delivery date in YYYY-MM-DD format.

    Returns
    -------
    bool
        True if the client is over 16 years old on delivery_date, False otherwise.
    """

    birth_datetime = datetime.strptime(date_of_birth, "%Y-%m-%d")
    delivery_datetime = datetime.strptime(delivery_date, "%Y-%m-%d")

    age = delivery_datetime.year - birth_datetime.year

    # Adjust if birthday hasn't occurred yet in the DOV month
    if (delivery_datetime.month < birth_datetime.month) or (
        delivery_datetime.month == birth_datetime.month
        and delivery_datetime.day < birth_datetime.day
    ):
        age -= 1

    return age >= 16


def calculate_age(DOB, DOV):
    """Calculate the age in years and months.

    Parameters
    ----------
    DOB : str
        Date of birth in YYYY-MM-DD format.
    DOV : str
        Date of visit in YYYY-MM-DD or Mon DD, YYYY format.

    Returns
    -------
    str
        Age string in format "YY Y MM M" (e.g., "5Y 3M").
    """
    DOB_datetime = datetime.strptime(DOB, "%Y-%m-%d")

    if DOV[0].isdigit():
        DOV_datetime = datetime.strptime(DOV, "%Y-%m-%d")
    else:
        DOV_datetime = datetime.strptime(DOV, "%b %d, %Y")

    years = DOV_datetime.year - DOB_datetime.year
    months = DOV_datetime.month - DOB_datetime.month

    if DOV_datetime.day < DOB_datetime.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}Y {months}M"

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


def build_preprocess_result(
    df: pd.DataFrame,
    language: str,
    disease_map: Dict[str, str],
    vaccine_reference: Dict[str, Any],
    ignore_agents: List[str],
) -> PreprocessResult:
    """Process and normalize client data into structured artifact.
    
    Calculates per-client age at time of delivery for determining
    communication recipient (parent vs. student).
    """
    warnings: set[str] = set()
    working = normalize_dataframe(df)
    
    # Load delivery_date from parameters.yaml for age calculations only
    params = {}
    if PARAMETERS_PATH.exists():
        params = yaml.safe_load(PARAMETERS_PATH.read_text(encoding="utf-8")) or {}
    delivery_date: Optional[str] = params.get("delivery_date")

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

    clients: List[ClientRecord] = []
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
        elif dob_iso and delivery_date:
            over_16 = over_16_check(dob_iso, delivery_date)
        else:
            over_16 = False

        person = {
            "full_name": " ".join(
                filter(None, [row.FIRST_NAME, row.LAST_NAME])
            ).strip(),
            "date_of_birth": dob_iso or "",
            "date_of_birth_display": formatted_dob or "",
            "date_of_birth_iso": dob_iso or "",
            "age": str(row.AGE) if not pd.isna(row.AGE) else "",
            "over_16": over_16,
        }

        school = {
            "name": row.SCHOOL_NAME,
            "id": row.SCHOOL_ID,
        }

        board = {
            "name": row.BOARD_NAME or "",
            "id": row.BOARD_ID,
        }

        contact = {
            "street": address_line,
            "city": row.CITY,
            "province": row.PROVINCE,
            "postal_code": postal_code,
        }

        client = ClientRecord(
            sequence=sequence,
            client_id=client_id,
            language=language,
            person=person,
            school=school,
            board=board,
            contact=contact,
            vaccines_due=vaccines_due if vaccines_due else None,
            vaccines_due_list=vaccines_due_list if vaccines_due_list else None,
            received=received if received else None,
            metadata={
                "unique_id": row.UNIQUE_ID or None,
            },
        )

        clients.append(client)

    return PreprocessResult(
        clients=clients,
        warnings=sorted(warnings),
    )


def write_artifact(
    output_dir: Path, language: str, run_id: str, result: PreprocessResult
) -> Path:
    """Write preprocessed result to JSON artifact file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create ArtifactPayload with rich metadata
    artifact_payload = ArtifactPayload(
        run_id=run_id,
        language=language,
        clients=result.clients,
        warnings=result.warnings,
        created_at=datetime.now(timezone.utc).isoformat(),
        total_clients=len(result.clients),
    )
    
    # Serialize to JSON (clients are dataclasses, so convert to dict)
    payload_dict = {
        "run_id": artifact_payload.run_id,
        "language": artifact_payload.language,
        "created_at": artifact_payload.created_at,
        "total_clients": artifact_payload.total_clients,
        "warnings": artifact_payload.warnings,
        "clients": [
            {
                "sequence": client.sequence,
                "client_id": client.client_id,
                "language": client.language,
                "person": {
                    "full_name": client.person["full_name"],
                    "date_of_birth": client.person["date_of_birth"],
                    "date_of_birth_display": client.person["date_of_birth_display"],
                    "date_of_birth_iso": client.person["date_of_birth_iso"],
                    "age": client.person["age"],
                    "over_16": client.person["over_16"],
                },
                "school": {
                    "name": client.school["name"],
                    "id": client.school["id"],
                },
                "board": {
                    "name": client.board["name"],
                    "id": client.board["id"],
                },
                "contact": {
                    "street": client.contact["street"],
                    "city": client.contact["city"],
                    "province": client.contact["province"],
                    "postal_code": client.contact["postal_code"],
                },
                "vaccines_due": client.vaccines_due,
                "vaccines_due_list": client.vaccines_due_list or [],
                "received": client.received or [],
                "metadata": client.metadata,
            }
            for client in artifact_payload.clients
        ],
    }
    
    artifact_path = output_dir / f"preprocessed_clients_{run_id}.json"
    artifact_path.write_text(json.dumps(payload_dict, indent=2), encoding="utf-8")
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
