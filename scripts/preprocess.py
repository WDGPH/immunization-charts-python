import argparse
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

try:  # Allow both package and script style execution
    from .utils import convert_date_iso, convert_date_string, convert_date_string_french
except ImportError:  # pragma: no cover - fallback for CLI execution
    from utils import convert_date_iso, convert_date_string, convert_date_string_french

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
DISEASE_MAP_PATH = CONFIG_DIR / "disease_map.json"
VACCINE_REFERENCE_PATH = CONFIG_DIR / "vaccine_reference.json"

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and normalize immunization data extracts into a single JSON artifact."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing the source extract.")
    parser.add_argument("input_file", type=str, help="Filename of the extract (CSV or Excel).")
    parser.add_argument("output_dir", type=Path, help="Directory where artifacts will be written.")
    parser.add_argument(
        "language",
        nargs="?",
        default="en",
        choices=["en", "fr"],
        help="Language code for downstream processing (default: en).",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        help="Optional run identifier used when naming artifacts (defaults to current UTC timestamp).",
    )
    return parser.parse_args(argv)


def configure_logging(output_dir: Path, run_id: str) -> Path:
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
    """Return the file extension for preprocessing logic"""
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
                except UnicodeDecodeError:
                    continue
                except pd.errors.ParserError:
                    continue
            else:
                raise ValueError("Could not decode CSV with common encodings or delimiters")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        logging.info(f"Loaded {len(df)} rows from {file_path}")
        return df

    except Exception as e:
        logging.error(f"Failed to read {file_path}: {e}")
        raise

def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [col.strip().upper() for col in df.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df.rename(columns=lambda x: x.replace(" ", "_"), inplace=True)
    df.rename(columns={"PROVINCE/TERRITORY": "PROVINCE"}, inplace=True)
    return df

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    # Standardize string columns we care about.
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
    existing = (existing or "").strip()
    if existing:
        return existing

    base = (source or "").strip().lower() or "unknown"
    digest = sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def process_vaccines_due(vaccines_due: Any, language: str, disease_map: Dict[str, str]) -> str:
    """Map diseases to vaccines using disease_map and handle language-specific cases."""
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


def process_received_agents(received_agents: Any, ignore_agents: List[str]) -> List[Dict[str, Any]]:
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
            grouped.append({
                "date_given": entry["date_given"],
                "vaccine": [entry["vaccine"]],
            })
        else:
            grouped[-1]["vaccine"].append(entry["vaccine"])

    return grouped


def enrich_grouped_records(
    grouped: List[Dict[str, Any]],
    vaccine_reference: Dict[str, Any],
    language: str,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for item in grouped:
        vaccines = [v.replace("-unspecified", "*").replace(" unspecified", "*") for v in item["vaccine"]]
        diseases = []
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


def build_preprocess_result(
    df: pd.DataFrame,
    language: str,
    disease_map: Dict[str, str],
    vaccine_reference: Dict[str, Any],
    ignore_agents: List[str],
) -> PreprocessResult:
    warnings: set[str] = set()
    working = normalize_dataframe(df)

    working["SCHOOL_ID"] = working.apply(
        lambda row: synthesize_identifier(row.get("SCHOOL_ID", ""), row["SCHOOL_NAME"], "sch"), axis=1
    )
    working["BOARD_ID"] = working.apply(
        lambda row: synthesize_identifier(row.get("BOARD_ID", ""), row.get("BOARD_NAME", ""), "brd"), axis=1
    )

    if (working["BOARD_NAME"] == "").any():
        affected = working.loc[working["BOARD_NAME"] == "", "SCHOOL_NAME"].unique().tolist()
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
        dob_iso = row.DATE_OF_BIRTH.strftime("%Y-%m-%d") if pd.notna(row.DATE_OF_BIRTH) else None
        if dob_iso is None:
            warnings.add(f"Missing date of birth for client {client_id}")

        formatted_dob = (
            convert_date_string_french(dob_iso) if language == "fr" and dob_iso else convert_date_string(dob_iso)
        )
        vaccines_due = process_vaccines_due(row.OVERDUE_DISEASE, language, disease_map)
        vaccines_due_list = [item.strip() for item in vaccines_due.split(",") if item.strip()]
        received_grouped = process_received_agents(row.IMMS_GIVEN, ignore_agents)
        received = enrich_grouped_records(received_grouped, vaccine_reference, language)

        postal_code = row.POSTAL_CODE if row.POSTAL_CODE else "Not provided"
        over_16 = bool(row.AGE >= 16) if not pd.isna(row.AGE) else False
        address_line = " ".join(filter(None, [row.STREET_ADDRESS_LINE_1, row.STREET_ADDRESS_LINE_2])).strip()

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
                "full_name": " ".join(filter(None, [row.FIRST_NAME, row.LAST_NAME])).strip(),
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
            },
        }
        clients.append(client_entry)


    return PreprocessResult(
        clients=clients,
        warnings=sorted(warnings),
    )


def write_artifact(output_dir: Path, language: str, run_id: str, result: PreprocessResult) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "language": language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_clients": len(result.clients),
        "clients": result.clients,
        "warnings": result.warnings,
    }
    artifact_path = output_dir / f"preprocessed_clients_{run_id}.json"
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logging.info("Wrote normalized artifact to %s", artifact_path)
    return artifact_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    log_path = configure_logging(args.output_dir, run_id)

    input_path = args.input_dir / args.input_file
    df_raw = read_input(input_path)
    df = ensure_required_columns(df_raw)

    disease_map = json.loads(DISEASE_MAP_PATH.read_text(encoding="utf-8"))
    vaccine_reference = json.loads(VACCINE_REFERENCE_PATH.read_text(encoding="utf-8"))

    result = build_preprocess_result(df, args.language, disease_map, vaccine_reference, IGNORE_AGENTS)

    artifact_path = write_artifact(args.output_dir / "artifacts", args.language, run_id, result)

    print(f"Structured data saved to {artifact_path}")
    print(f"Preprocess log written to {log_path}")
    if result.warnings:
        print("Warnings detected during preprocessing:")
        for warning in result.warnings:
            print(f" - {warning}")
    
    return 0


if __name__ == "__main__":
    main()