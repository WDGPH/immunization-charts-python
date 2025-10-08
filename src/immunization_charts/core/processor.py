"""
Core data processing for immunization charts.

This module contains the main ClientDataProcessor class that handles
the transformation of vaccination and demographic data into structured notices.
"""

import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..utils.date_utils import (
    convert_date_iso,
    convert_date_string,
    convert_date_string_french,
)

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "config"))
from settings import config

logger = logging.getLogger(__name__)


class ClientDataProcessor:
    """Handles per-client transformation of vaccination and demographic data into structured notices."""

    def __init__(
        self,
        df: pd.DataFrame,
        disease_map: Optional[Dict[str, str]] = None,
        vaccine_ref: Optional[Dict[str, Any]] = None,
        ignore_agents: Optional[List[str]] = None,
        delivery_date: Optional[str] = None,
        language: str = "english",
    ):
        """Initialize the ClientDataProcessor.

        Args:
            df: Raw client data DataFrame
            disease_map: Maps disease descriptions to vaccine names
            vaccine_ref: Maps vaccines to diseases
            ignore_agents: Agents to skip during processing
            delivery_date: Processing run date (e.g., "2024-06-01")
            language: Language code ("english" or "french")
        """
        self.df = df.copy()
        self.disease_map = disease_map or config.disease_map
        self.vaccine_ref = vaccine_ref or config.vaccine_reference
        self.ignore_agents = ignore_agents or config.ignore_agents
        self.delivery_date = delivery_date or config.delivery_date
        self.language = language

        # Initialize notices structure
        self.notices = defaultdict(
            lambda: {
                "name": "",
                "school": "",
                "date_of_birth": "",
                "age": "",
                "over_16": "",
                "received": [],
            }
        )

        logger.info(
            f"Initialized ClientDataProcessor for {len(df)} clients in {language}"
        )

    def process_vaccines_due(self, vaccines_due: str) -> str:
        """Map diseases to vaccines using disease_map and handle language-specific cases.

        Args:
            vaccines_due: Comma-separated string of diseases

        Returns:
            Mapped vaccine names as comma-separated string
        """
        if not vaccines_due:
            return ""

        vaccines_updated = []
        for v in vaccines_due.split(", "):
            v_clean = v.strip()

            # Language-specific replacements
            if (
                self.language == "english"
                and v_clean == "Haemophilus influenzae infection, invasive"
            ):
                v_clean = "Invasive Haemophilus influenzae infection (Hib)"
            elif (
                self.language == "french"
                and v_clean == "infection à Haemophilus influenzae, invasive"
            ):
                v_clean = "Haemophilus influenzae de type b (Hib)"

            mapped = self.disease_map.get(v_clean, v_clean)
            vaccines_updated.append(mapped)

        return (
            ", ".join(vaccines_updated).replace("'", "").replace('"', "").rstrip(", ")
        )

    def process_received_agents(self, received_agents: str) -> List[List[str]]:
        """Extract and normalize vaccination history from received agents string.

        Args:
            received_agents: String containing vaccination history

        Returns:
            List of [date, vaccine] pairs sorted by date
        """
        matches = re.findall(r"\w{3} \d{1,2}, \d{4} - [^,]+", received_agents)
        vax_date = []

        for m in matches:
            date_str, vaccine = m.split(" - ")
            date_str = convert_date_iso(date_str.strip())

            if vaccine in self.ignore_agents:
                continue

            vax_date.append([date_str, vaccine.strip()])

        vax_date.sort(key=lambda x: x[0])
        return vax_date

    def build_notices(self) -> None:
        """Build structured notices for all clients in the DataFrame."""
        logger.info(f"Building notices for {len(self.df)} clients")

        for _, row in self.df.iterrows():
            client_id = row.CLIENT_ID
            self.notices[client_id]["name"] = f"{row.FIRST_NAME} {row.LAST_NAME}"

            # Clean school name
            row.SCHOOL_NAME = row.SCHOOL_NAME.replace("_", " ")
            self.notices[client_id]["school"] = row.SCHOOL_NAME

            # Format date of birth based on language
            if self.language == "french":
                self.notices[client_id]["date_of_birth"] = convert_date_string_french(
                    row.DATE_OF_BIRTH
                )
            else:
                self.notices[client_id]["date_of_birth"] = convert_date_string(
                    row.DATE_OF_BIRTH
                )

            # Address information
            self.notices[client_id]["address"] = row.STREET_ADDRESS
            self.notices[client_id]["city"] = row.CITY
            self.notices[client_id]["postal_code"] = (
                row.POSTAL_CODE
                if pd.notna(row.POSTAL_CODE) and row.POSTAL_CODE != ""
                else "Not provided"
            )
            self.notices[client_id]["province"] = row.PROVINCE
            self.notices[client_id]["over_16"] = row.AGE > 16

            # Process vaccines due
            self.notices[client_id]["vaccines_due"] = self.process_vaccines_due(
                row.OVERDUE_DISEASE
            )

            # Process vaccination history
            vax_date_list = self.process_received_agents(row.IMMS_GIVEN)
            i = 0

            while i < len(vax_date_list):
                vax_list = []
                disease_list = []

                date_str, vaccine = vax_date_list[i]
                vax_list.append(vaccine)

                # Group vaccines with the same date
                for j in range(i + 1, len(vax_date_list)):
                    date_str_next, vaccine_next = vax_date_list[j]

                    if date_str == date_str_next:
                        vax_list.append(vaccine_next)
                        i += 1
                    else:
                        break

                # Map vaccines to diseases
                disease_list = [self.vaccine_ref.get(v, v) for v in vax_list]

                # Flatten disease lists
                disease_list = [
                    d
                    for sublist in disease_list
                    for d in (sublist if isinstance(sublist, list) else [sublist])
                ]

                # Replace 'unspecified' vaccines
                vax_list = [
                    v.replace("-unspecified", "*").replace(" unspecified", "*")
                    for v in vax_list
                ]

                # Translate to French if needed
                if self.language == "french":
                    disease_list = [self.vaccine_ref.get(d, d) for d in disease_list]

                self.notices[client_id]["received"].append(
                    {
                        "date_given": date_str,
                        "vaccine": vax_list,
                        "diseases": disease_list,
                    }
                )
                i += 1

    def save_output(self, outdir: Path, filename: str) -> None:
        """Save processed notices to JSON and CSV files.

        Args:
            outdir: Output directory
            filename: Base filename for output files
        """
        outdir.mkdir(parents=True, exist_ok=True)
        notices_dict = dict(self.notices)

        # Save client IDs
        client_ids_df = pd.DataFrame(list(notices_dict.keys()), columns=["Client_ID"])
        client_ids_df.to_csv(
            outdir / f"{filename}_client_ids.csv", index=False, header=False
        )

        # Save JSON
        with open(outdir / f"{filename}.json", "w") as f:
            json.dump(notices_dict, f, indent=4)

        logger.info(f"Structured data saved to {outdir / f'{filename}.json'}")
        logger.info(f"Client IDs saved to {outdir / f'{filename}_client_ids.csv'}")

    def get_notices(self) -> Dict[str, Any]:
        """Get the processed notices dictionary.

        Returns:
            Dictionary of processed notices
        """
        return dict(self.notices)
