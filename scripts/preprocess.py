"""
Preprocessing pipeline for immunization-charts.
Replaces run_pipeline with Python orchestrator
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
import yaml 
import glob
import json
import re
from collections import defaultdict
from string import Formatter
from typing import Any, Dict, Optional, Set
from utils import convert_date_string_french, over_16_check, convert_date_iso, convert_date_string

logging.basicConfig(
    filename = "preprocess.log",
    level = logging.INFO,

)

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
    "language",
    "language_code",
}

DEFAULT_QR_PAYLOAD_TEMPLATE = {
    "english": "https://www.test-immunization.ca/update?client_id={client_id}&dob={date_of_birth_iso}",
    "french": "https://www.test-immunization.ca/update?client_id={client_id}&dob={date_of_birth_iso}",
}


class ClientDataProcessor:
    def __init__(self, df: pd.DataFrame, disease_map: dict, vaccine_ref: dict,
                ignore_agents: list, delivery_date: str, language: str = "en",
                qr_payload_template: Optional[str] = None,
                allowed_template_fields: Optional[Set[str]] = None):
        self.df = df.copy()
        self.disease_map = disease_map
        self.vaccine_ref = vaccine_ref
        self.ignore_agents = ignore_agents
        self.delivery_date = delivery_date
        self.language = language
        base_allowed_fields = set(SUPPORTED_QR_TEMPLATE_FIELDS)
        if allowed_template_fields:
            base_allowed_fields |= set(allowed_template_fields)
        self.allowed_template_fields = base_allowed_fields
        self.qr_payload_template = qr_payload_template
        self.formatter = Formatter()
        self.notices = defaultdict(lambda: {
            "name": "",
            "school": "",
            "date_of_birth": "",
            "age": "",
            "over_16": "",
            "received": [],
            "qr_code": "",  # File path to QR code image
            "qr_payload": "",
        })

    def process_vaccines_due(self, vaccines_due: str) -> str:
        """Map diseases to vaccines using disease_map and handle language-specific cases."""
        if not vaccines_due:
            return ""
        vaccines_updated = []
        for v in vaccines_due.split(', '):
            v_clean = v.strip()
            # language-specific replacements
            if self.language == 'english' and v_clean == 'Haemophilus influenzae infection, invasive':
                v_clean = 'Invasive Haemophilus influenzae infection (Hib)'
            elif self.language == 'french' and v_clean == 'infection à Haemophilus influenzae, invasive':
                v_clean = 'Haemophilus influenzae de type b (Hib)'
            mapped = self.disease_map.get(v_clean, v_clean)
            vaccines_updated.append(mapped)
        return ', '.join(vaccines_updated).replace("'", "").replace('"', '').rstrip(', ')

    def process_received_agents(self, received_agents: str):
        matches = re.findall(r'\w{3} \d{1,2}, \d{4} - [^,]+', received_agents)
        vax_date = []
        for m in matches:
            date_str, vaccine = m.split(' - ')
            date_str = convert_date_iso(date_str.strip())
            if vaccine in self.ignore_agents:
                continue
            vax_date.append([date_str, vaccine.strip()])
        vax_date.sort(key=lambda x: x[0])
        return vax_date

    def _safe_str(self, value) -> str:
        if pd.isna(value):
            return ""
        return str(value).strip()

    def _build_template_context(self, row: pd.Series, client_id: str, dob_label: str) -> Dict[str, Any]:
        dob_iso = self._safe_str(row.DATE_OF_BIRTH if "DATE_OF_BIRTH" in row else row.get("DATE_OF_BIRTH"))
        context = {
            "client_id": str(client_id),
            "first_name": self._safe_str(row.FIRST_NAME),
            "last_name": self._safe_str(row.LAST_NAME),
            "name": f"{self._safe_str(row.FIRST_NAME)} {self._safe_str(row.LAST_NAME)}".strip(),
            "date_of_birth": dob_label,
            "date_of_birth_iso": dob_iso,
            "school": self._safe_str(row.SCHOOL_NAME),
            "city": self._safe_str(row.CITY),
            "postal_code": self._safe_str(row.POSTAL_CODE),
            "province": self._safe_str(row.PROVINCE),
            "street_address": self._safe_str(row.STREET_ADDRESS),
            "language": self.language,
            "language_code": "fr" if self.language.startswith("fr") else "en",
            "delivery_date": self._safe_str(self.delivery_date),
        }
        return context

    def _format_template(self, template: str, context: Dict[str, Any], source_key: str) -> str:
        if template is None:
            return ""
        try:
            fields = {field_name for _, field_name, _, _ in self.formatter.parse(template) if field_name}
        except ValueError as exc:
            raise ValueError(f"Invalid format string in {source_key}: {exc}") from exc

        unknown_fields = fields - context.keys()
        if unknown_fields:
            raise KeyError(
                f"Unknown placeholder(s) {unknown_fields} in {source_key}. "
                f"Available placeholders: {sorted(context.keys())}"
            )

        disallowed = fields - self.allowed_template_fields
        if disallowed:
            raise ValueError(
                f"Disallowed placeholder(s) {disallowed} in {source_key}. "
                f"Allowed placeholders: {sorted(self.allowed_template_fields)}"
            )

        return template.format(**context)

    def _build_qr_payload(self, context: Dict[str, Any], default_payload: str) -> str:
        if not self.qr_payload_template:
            return default_payload
        return self._format_template(self.qr_payload_template, context, "qr_payload_template")
    
    def build_notices(self):
        from utils import generate_qr_code
        
        for _, row in self.df.iterrows():
            client_id = row.CLIENT_ID
            self.notices[client_id]["name"] = f"{row.FIRST_NAME} {row.LAST_NAME}"
            row.SCHOOL_NAME = row.SCHOOL_NAME.replace("_", " ")
            self.notices[client_id]["school"] = row.SCHOOL_NAME
            dob_label = (
                convert_date_string_french(row.DATE_OF_BIRTH) if self.language == 'french'
                else convert_date_string(row.DATE_OF_BIRTH)
            )
            self.notices[client_id]["date_of_birth"] = dob_label

            context = self._build_template_context(row, client_id, dob_label)

            # Generate QR code with client information
            qr_data = {
                "id": client_id,
                "name": f"{row.FIRST_NAME} {row.LAST_NAME}",
                "dob": row.DATE_OF_BIRTH,
                "school": row.SCHOOL_NAME
            }
            default_qr_payload = json.dumps(qr_data, sort_keys=True)
            qr_payload = self._build_qr_payload(context, default_qr_payload)
            self.notices[client_id]["qr_payload"] = qr_payload
            self.notices[client_id]["qr_code"] = generate_qr_code(qr_payload, client_id)
            self.notices[client_id]["address"] = row.STREET_ADDRESS
            self.notices[client_id]["city"] = row.CITY
            self.notices[client_id]["postal_code"] = row.POSTAL_CODE if pd.notna(row.POSTAL_CODE) and row.POSTAL_CODE != "" else "Not provided"
            self.notices[client_id]["province"] = row.PROVINCE
            age_value = row.get("AGE")
            if age_value is not None and not pd.isna(age_value):
                over_16 = age_value > 16
            else:
                over_16 = over_16_check(row.DATE_OF_BIRTH, self.delivery_date) if self.delivery_date else False
            self.notices[client_id]["over_16"] = over_16
            self.notices[client_id]["vaccines_due"] = self.process_vaccines_due(row.OVERDUE_DISEASE) 

            vax_date_list = self.process_received_agents(row.IMMS_GIVEN)
            i = 0
            while i < len(vax_date_list):

                vax_list = []
                disease_list = []

                date_str, vaccine = vax_date_list[i]
                vax_list.append(vaccine)

                # group vaccines with the same date
                for j in range(i + 1, len(vax_date_list)):

                    date_str_next, vaccine_next = vax_date_list[j]

                    if date_str == date_str_next:
                        vax_list.append(vaccine_next)
                        i += 1
                    else:
                        break
                
                disease_list = [self.vaccine_ref.get(v, v) for v in vax_list]
                # flatten disease lists 
                disease_list = [d for sublist in disease_list for d in (sublist if isinstance(sublist, list) else [sublist])]
                # replace 'unspecified' vaccines
                vax_list = [v.replace('-unspecified', '*').replace(' unspecified', '*') for v in vax_list]
                # translate to French if needed
                if self.language == 'french':
                    disease_list = [self.vaccine_ref.get(d, d) for d in disease_list]
                self.notices[client_id]["received"].append({"date_given": date_str, "vaccine": vax_list, "diseases": disease_list})
                i += 1

    def save_output(self, outdir: Path, filename: str):
        outdir.mkdir(parents=True, exist_ok=True)
        notices_dict = dict(self.notices)
        # save client ids
        client_ids_df = pd.DataFrame(list(notices_dict.keys()), columns=["Client_ID"])
        client_ids_df.to_csv(outdir / f"{filename}_client_ids.csv", index=False, header=False)
        # save JSON
        with open(outdir / f"{filename}.json", 'w') as f:
            json.dump(notices_dict, f, indent=4)
        print(f"Structured data saved to {outdir / f'{filename}.json'}")


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

def separate_by_column(data: pd.DataFrame, col_name: str, out_path: Path):
    """
    Group a DataFrame by a column and save each group to a separate CSV
    """
    out_path.mkdir(parents=True, exist_ok=True)

    if col_name not in data.columns:
        raise ValueError(f"Column {col_name} not found in DataFrame")
    
    grouped = data.groupby(col_name)

    for name, group in grouped:
    
        safe_name = str(name).replace(" ", "_").replace("/", "_").replace("-","_").replace(".","").upper()
        output_file = f"{out_path}/{safe_name}.csv"  # Save as CSV
        
        print(f"Processing group: {safe_name}")
        group.to_csv(output_file, index=False, sep=";")
        logging.info(f"Saved group {safe_name} with {len(group)} rows to {output_file}")


def split_batches(input_dir: Path, output_dir: Path, batch_size: int):
    """
    Split CSV files in input_dir into batches of size batch_size
    and save them in output_dir
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_files = list(input_dir.glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {input_dir}")
        return

    for file in csv_files:
        df = pd.read_csv(file, sep=";", engine="python", encoding="latin-1", quotechar='"')
        filename_base = file.stem

        # Split into batches
        num_batches = (len(df) + batch_size - 1) // batch_size  # ceiling division
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size
            batch_df = df.iloc[start_idx:end_idx]

            batch_file = output_dir / f"{filename_base}_{i+1:02d}.csv"
            batch_df.to_csv(batch_file, index=False, sep=";")
            print(f"Saved batch: {batch_file} ({len(batch_df)} rows)")

def check_file_existence(file_path: Path) -> bool:
    """Check if a file exists and is accessible."""
    exists = file_path.exists() and file_path.is_file()
    if exists:
        logging.info(f"File exists: {file_path}")
    else:
        logging.warning(f"File does not exist: {file_path}")
    return exists

def load_data(input_file: str) -> pd.DataFrame:
    """Load and clean data from input file."""
    df = read_input(Path(input_file))

    # Replace column names with uppercase 
    df.columns = [col.strip().upper() for col in df.columns]
    logging.info(f"Columns after loading: {df.columns.tolist()}")

    return df

def validate_transform_columns(df: pd.DataFrame, required_columns: list):
    """Validate that required columns are present in the DataFrame."""
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols} in DataFrame with columns {df.columns.tolist()}")
    
    # Rename columns to have underscores instead of spaces
    df.rename(columns=lambda x: x.replace(" ", "_"), inplace=True)

    # Rename PROVINCE/TERRITORY to PROVINCE
    df.rename(columns={"PROVINCE/TERRITORY": "PROVINCE"}, inplace=True)

    logging.info("All required columns are present.")

def separate_by_school(df: pd.DataFrame, output_dir: str, school_column: str = "School Name"):
    """
    Separates the DataFrame by school/daycare and writes separate CSVs.

    Args:
        df (pd.DataFrame): Cleaned DataFrame.
        output_dir (str): Path to directory where CSVs will be saved.
        school_column (str): Column to separate by (default "School Name").
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logging.info(f"Separating data by {school_column}...")
    separate_by_column(df, school_column, output_path)
    logging.info(f"Data separated by {school_column}. Files saved to {output_path}.")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python preprocess.py <input_dir> <input_file> <output_dir> [language]")
        sys.exit(1)
    
    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "POSTAL CODE",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
    ]

    input_dir = sys.argv[1]
    input_file = sys.argv[2]
    output_dir = sys.argv[3]
    language = sys.argv[4] if len(sys.argv) > 4 else "english"

    if language not in ["english", "french"]:
        print("Error: Language must be 'english' or 'french'")
        sys.exit(1)

    output_dir_school = output_dir + "/by_school"
    output_dir_batch = output_dir + "/batches"
    output_dir_final = output_dir + "/json_" + language

    df = load_data(input_dir + '/' + input_file)
    validate_transform_columns(df, required_columns) #FIXME make required_columns come from a config file
    separate_by_school(df, output_dir_school, "SCHOOL_NAME")

    # Step 3: Split by batch size
    batch_size = 100  # FIXME make this come from a config file
    batch_dir = Path(output_dir + "/batches")
    split_batches(Path(output_dir_school), Path(batch_dir), batch_size)
    logging.info("Completed splitting into batches.")

    all_batch_files = sorted(batch_dir.glob("*.csv"))

    config_dir = Path("../config")
    disease_map_path = config_dir / "disease_map.json"
    vaccine_ref_path = config_dir / "vaccine_reference.json"
    qr_config_path = config_dir / "qr_config.yaml"

    with open(disease_map_path, "r") as disease_map_file:
        disease_map = json.load(disease_map_file)
    with open(vaccine_ref_path, "r") as vaccine_ref_file:
        vaccine_ref = json.load(vaccine_ref_file)

    qr_config: Dict[str, Any] = {}
    if qr_config_path.exists():
        with open(qr_config_path, "r") as qr_config_file:
            qr_config = yaml.safe_load(qr_config_file) or {}
    else:
        logging.info("QR configuration not found at %s; using default payload template.", qr_config_path)

    qr_payload_template = DEFAULT_QR_PAYLOAD_TEMPLATE.get(language)
    qr_template_config = qr_config.get("qr_payload_template")
    if isinstance(qr_template_config, dict):
        qr_payload_template = qr_template_config.get(language, qr_payload_template)
    elif isinstance(qr_template_config, str):
        qr_payload_template = qr_template_config

    allowed_placeholder_overrides = qr_config.get("allowed_placeholders")
    if isinstance(allowed_placeholder_overrides, (list, set, tuple)):
        allowed_placeholder_set = set(allowed_placeholder_overrides)
    else:
        allowed_placeholder_set = set()
        if allowed_placeholder_overrides not in (None, []):
            logging.warning("Ignoring invalid allowed_placeholders configuration: expected a list of strings.")

    delivery_date_value = qr_config.get("delivery_date", "2024-06-01")

    for batch_file in all_batch_files:
        print(f"Processing batch file: {batch_file}")
        df_batch = pd.read_csv(batch_file, sep=";", engine="python", encoding="latin-1", quotechar='"')

        if 'STREET_ADDRESS_LINE_2' in df_batch.columns:
            df_batch['STREET_ADDRESS'] = df_batch['STREET_ADDRESS_LINE_1'].fillna('') + ' ' + df_batch['STREET_ADDRESS_LINE_2'].fillna('')
            df_batch.drop(columns=['STREET_ADDRESS_LINE_1', 'STREET_ADDRESS_LINE_2'], inplace=True)

        processor = ClientDataProcessor(
            df=df_batch,
            disease_map=disease_map,
            vaccine_ref=vaccine_ref,
            ignore_agents=["-unspecified", "unspecified", "Not Specified", "Not specified", "Not Specified-unspecified"],
            delivery_date=delivery_date_value,
            language=language,
            qr_payload_template=qr_payload_template,
            allowed_template_fields=allowed_placeholder_set or None,
        )
        processor.build_notices()
        processor.save_output(Path(output_dir_final), batch_file.stem)
        logging.info("Preprocessing completed successfully.")
