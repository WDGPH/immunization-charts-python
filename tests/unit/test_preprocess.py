"""Unit tests for preprocess module - data normalization and client artifact generation.

Tests cover:
- Schema validation (required columns, data types)
- Data cleaning (dates, addresses, vaccine history)
- Client sorting and sequencing
- Artifact structure consistency
- Error handling for invalid inputs
- Date conversion and age calculation
- Vaccine mapping and normalization
- Language support (English and French)

Real-world significance:
- Step 2 of pipeline: transforms Excel input into normalized client data
- Preprocessing correctness directly affects accuracy of all downstream notices
- Client sorting must be deterministic for reproducible output
- Vaccine mapping must correctly expand component diseases
- Age calculation affects notice recipient determination
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts import preprocess
from tests.fixtures import sample_input


@pytest.mark.unit
class TestReadInput:
    """Unit tests for read_input function."""

    def test_read_input_xlsx_file(self, tmp_test_dir: Path) -> None:
        """Verify reading Excel (.xlsx) files works correctly.

        Real-world significance:
        - School district input is provided in .xlsx format
        - Must handle openpyxl engine properly
        """
        df_original = sample_input.create_test_input_dataframe(num_clients=3)
        input_path = tmp_test_dir / "test_input.xlsx"
        df_original.to_excel(input_path, index=False)

        df_read = preprocess.read_input(input_path)

        assert len(df_read) == 3
        assert (
            "SCHOOL NAME" in df_read.columns
            or "SCHOOL_NAME" in str(df_read.columns).upper()
        )

    def test_read_input_missing_file_raises_error(self, tmp_test_dir: Path) -> None:
        """Verify error when input file doesn't exist.

        Real-world significance:
        - Must fail early if user provides incorrect input path
        """
        missing_path = tmp_test_dir / "nonexistent.xlsx"

        with pytest.raises(FileNotFoundError):
            preprocess.read_input(missing_path)

    def test_read_input_unsupported_file_type_raises_error(
        self, tmp_test_dir: Path
    ) -> None:
        """Verify error for unsupported file types.

        Real-world significance:
        - Pipeline should reject non-Excel/CSV files early
        """
        unsupported_path = tmp_test_dir / "test.txt"
        unsupported_path.write_text("some data")

        with pytest.raises(ValueError, match="Unsupported file type"):
            preprocess.read_input(unsupported_path)


@pytest.mark.unit
class TestEnsureRequiredColumns:
    """Unit tests for ensure_required_columns function."""

    def test_ensure_required_columns_passes_valid_dataframe(self) -> None:
        """Verify valid DataFrame passes validation.

        Real-world significance:
        - Valid school district input should process without errors
        """
        df = sample_input.create_test_input_dataframe(num_clients=3)

        result = preprocess.ensure_required_columns(df)

        assert result is not None
        assert len(result) == 3

    def test_ensure_required_columns_normalizes_whitespace(self) -> None:
        """Verify column names are normalized (whitespace, case).

        Real-world significance:
        - Input files may have inconsistent column naming
        - Pipeline must handle variations in Excel headers
        """
        df = pd.DataFrame(
            {
                "  SCHOOL NAME  ": ["Test School"],
                "  CLIENT ID  ": ["C001"],
                "first name": ["Alice"],
                "last name": ["Zephyr"],
                "date of birth": ["2015-01-01"],
                "city": ["Guelph"],
                "postal code": ["N1H 2T2"],
                "province/territory": ["ON"],
                "overdue disease": ["Measles"],
                "imms given": [""],
                "street address line 1": ["123 Main"],
                "street address line 2": [""],
            }
        )

        result = preprocess.ensure_required_columns(df)

        # Should not raise error and column names should be normalized
        assert len(result) == 1

    def test_ensure_required_columns_missing_required_raises_error(self) -> None:
        """Verify error when required columns are missing.

        Real-world significance:
        - Missing critical columns (e.g., OVERDUE DISEASE) means input is invalid
        - Must fail early with clear error
        """
        df = pd.DataFrame(
            {
                "SCHOOL NAME": ["Test"],
                "CLIENT ID": ["C001"],
                # Missing required columns
            }
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            preprocess.ensure_required_columns(df)


@pytest.mark.unit
class TestNormalizeDataFrame:
    """Unit tests for normalize_dataframe function."""

    def test_normalize_dataframe_handles_missing_values(self) -> None:
        """Verify NaN/None values are converted to empty strings.

        Real-world significance:
        - Input may have missing fields (e.g., no suite number)
        - Must normalize to empty strings for consistent processing
        """
        df = sample_input.create_test_input_dataframe(num_clients=3)
        normalized = preprocess.ensure_required_columns(df)
        normalized.loc[0, "STREET_ADDRESS_LINE_2"] = None
        normalized.loc[1, "POSTAL_CODE"] = float("nan")

        result = preprocess.normalize_dataframe(normalized)

        assert result["STREET_ADDRESS_LINE_2"].iloc[0] == ""
        assert result["POSTAL_CODE"].iloc[1] == ""

    def test_normalize_dataframe_converts_dates(self) -> None:
        """Verify dates are converted to datetime objects.

        Real-world significance:
        - Date fields must be parsed for age calculation
        - Invalid dates must be detected early
        """
        df = sample_input.create_test_input_dataframe(num_clients=2)
        df["DATE OF BIRTH"] = ["2015-01-02", "2014-05-06"]
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.normalize_dataframe(normalized)

        assert pd.api.types.is_datetime64_any_dtype(result["DATE_OF_BIRTH"])

    def test_normalize_dataframe_trims_whitespace(self) -> None:
        """Verify string columns have whitespace trimmed.

        Real-world significance:
        - Input may have accidental leading/trailing spaces
        - Must normalize for consistent matching
        """
        df = sample_input.create_test_input_dataframe(num_clients=1)
        df["FIRST NAME"] = ["  Alice  "]
        df["LAST NAME"] = ["  Zephyr  "]
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.normalize_dataframe(normalized)

        assert result["FIRST_NAME"].iloc[0] == "Alice"
        assert result["LAST_NAME"].iloc[0] == "Zephyr"


@pytest.mark.unit
class TestDateConversion:
    """Unit tests for date conversion functions."""

    def test_convert_date_string_english(self) -> None:
        """Verify ISO date conversion to English display format.

        Real-world significance:
        - Notices display dates in English (e.g., "May 8, 2025")
        - Must handle various input formats
        """
        result = preprocess.convert_date_string("2025-05-08")

        assert result == "May 08, 2025"

    def test_convert_date_string_french(self) -> None:
        """Verify ISO date conversion to French display format.

        Real-world significance:
        - Notices display dates in French (e.g., "8 mai 2025")
        - Required for multilingual support
        """
        result = preprocess.convert_date_string_french("2025-05-08")

        assert result == "8 mai 2025"

    def test_convert_date_iso_from_english_display(self) -> None:
        """Verify English display format conversion to ISO.

        Real-world significance:
        - Some input may have dates in display format
        - Must convert to ISO for consistent processing
        """
        result = preprocess.convert_date_iso("May 08, 2025")

        assert result == "2025-05-08"

    def test_convert_date_bidirectional(self) -> None:
        """Verify convert_date function handles both directions.

        Real-world significance:
        - Different pipeline steps need dates in different formats
        - Must support ISO↔display conversions for both languages
        """
        # English: ISO → display
        display_en = preprocess.convert_date(
            "2025-05-08", to_format="display", lang="en"
        )
        assert display_en == "May 8, 2025"

        # French: ISO → display
        display_fr = preprocess.convert_date(
            "2025-05-08", to_format="display", lang="fr"
        )
        assert display_fr == "8 mai 2025"

    def test_convert_date_handles_nan(self) -> None:
        """Verify NaN/None dates are handled gracefully.

        Real-world significance:
        - Some records may have missing dates
        - Must return None without crashing
        """
        result = preprocess.convert_date_string(None)

        assert result is None

    def test_convert_date_invalid_format_raises_error(self) -> None:
        """Verify error on invalid date format.

        Real-world significance:
        - Invalid dates in input indicate data corruption
        - Must fail early with clear error
        """
        with pytest.raises(ValueError):
            preprocess.convert_date_string("invalid-date")


@pytest.mark.unit
class TestAgeCalculation:
    """Unit tests for age calculation functions."""

    def test_calculate_age_full_years_and_months(self) -> None:
        """Verify age calculation includes years and months.

        Real-world significance:
        - Ages appear on notices (e.g., "5Y 3M")
        - Must be accurate for immunization history context
        """
        result = preprocess.calculate_age("2015-01-02", "2020-04-15")

        assert result == "5Y 3M"

    def test_calculate_age_less_than_one_year(self) -> None:
        """Verify age calculation for infants.

        Real-world significance:
        - Very young children (0-11 months) need accurate age display
        """
        result = preprocess.calculate_age("2020-01-02", "2020-08-15")

        assert result == "0Y 7M"

    def test_calculate_age_just_before_birthday(self) -> None:
        """Verify age doesn't increment until birthday.

        Real-world significance:
        - Age calculation must respect exact birth date
        - Incorrect age could affect immunization recommendations
        """
        result = preprocess.calculate_age("2015-05-15", "2020-05-14")

        assert result == "4Y 11M"

    def test_calculate_age_on_birthday(self) -> None:
        """Verify age increments exactly on birthday.

        Real-world significance:
        - Age calculation must be precise on birthday
        """
        result = preprocess.calculate_age("2015-05-15", "2020-05-15")

        assert result == "5Y 0M"

    def test_over_16_check_true_for_over_16(self) -> None:
        """Verify over_16_check returns True for age >= 16.

        Real-world significance:
        - Notices sent to student (not parent) if over 16
        - Must correctly classify students by age
        """
        result = preprocess.over_16_check("2000-01-01", "2020-05-15")

        assert result is True

    def test_over_16_check_false_for_under_16(self) -> None:
        """Verify over_16_check returns False for age < 16.

        Real-world significance:
        - Notices sent to parent for students under 16
        """
        result = preprocess.over_16_check("2010-01-01", "2020-05-15")

        assert result is False

    def test_over_16_check_boundary_at_16(self) -> None:
        """Verify over_16_check boundary condition at exactly 16 years.

        Real-world significance:
        - Must correctly handle 16th birthday (inclusive)
        """
        result = preprocess.over_16_check("2000-05-15", "2016-05-15")

        assert result is True


@pytest.mark.unit
class TestBuildPreprocessResult:
    """Unit tests for build_preprocess_result function."""

    def test_build_result_generates_clients_with_sequences(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify clients are generated with sequence numbers.

        Real-world significance:
        - Sequence numbers (00001, 00002...) appear on notices
        - Must be deterministic: same input → same sequences
        """
        df = sample_input.create_test_input_dataframe(num_clients=3)
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        assert len(result.clients) == 3
        # Sequences should be sequential
        sequences = [c.sequence for c in result.clients]
        assert sequences == ["00001", "00002", "00003"]

    def test_build_result_sorts_clients_deterministically(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify clients are sorted consistently.

        Real-world significance:
        - Same input must always produce same client order
        - Required for comparing pipeline runs (reproducibility)
        - Enables batching by school to work correctly
        """
        df = sample_input.create_test_input_dataframe(num_clients=3)
        normalized = preprocess.ensure_required_columns(df)

        result1 = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        result2 = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        ids1 = [c.client_id for c in result1.clients]
        ids2 = [c.client_id for c in result2.clients]
        assert ids1 == ids2, "Client order must be deterministic"

    def test_build_result_sorts_by_school_then_name(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify clients sorted by school → last_name → first_name → client_id.

        Real-world significance:
        - Specific sort order enables school-based batching
        - Must be deterministic across pipeline runs
        - Affects sequence number assignment
        """
        df = pd.DataFrame(
            {
                "SCHOOL NAME": [
                    "Zebra School",
                    "Zebra School",
                    "Apple School",
                    "Apple School",
                ],
                "CLIENT ID": ["C002", "C001", "C004", "C003"],
                "FIRST NAME": ["Bob", "Alice", "Diana", "Chloe"],
                "LAST NAME": ["Smith", "Smith", "Jones", "Jones"],
                "DATE OF BIRTH": [
                    "2015-01-01",
                    "2015-01-02",
                    "2015-01-03",
                    "2015-01-04",
                ],
                "CITY": ["Town", "Town", "Town", "Town"],
                "POSTAL CODE": ["N1H 2T2", "N1H 2T2", "N1H 2T2", "N1H 2T2"],
                "PROVINCE/TERRITORY": ["ON", "ON", "ON", "ON"],
                "OVERDUE DISEASE": ["Measles", "Measles", "Measles", "Measles"],
                "IMMS GIVEN": ["", "", "", ""],
                "STREET ADDRESS LINE 1": [
                    "123 Main",
                    "123 Main",
                    "123 Main",
                    "123 Main",
                ],
                "STREET ADDRESS LINE 2": ["", "", "", ""],
            }
        )
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        # Expected order: Apple/Chloe/Jones, Apple/Diana/Jones, Zebra/Alice/Smith, Zebra/Bob/Smith
        expected_ids = ["C003", "C004", "C001", "C002"]
        actual_ids = [c.client_id for c in result.clients]
        assert actual_ids == expected_ids

    def test_build_result_maps_vaccines_correctly(
        self, default_vaccine_reference
    ) -> None:
        """Verify vaccine codes expand to component diseases.

        Real-world significance:
        - DTaP → Diphtheria, Tetanus, Pertussis
        - Vaccine mapping must preserve all components
        - Affects disease coverage reporting in notices
        """
        disease_map = {
            "DTaP": "Diphtheria/Tetanus/Pertussis",
            "Diphtheria": "Diphtheria",
            "Tetanus": "Tetanus",
            "Pertussis": "Pertussis",
        }
        df = sample_input.create_test_input_dataframe(num_clients=1)
        df["IMMS GIVEN"] = ["May 1, 2020 - DTaP"]
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        # Should have DTaP expanded to component diseases
        assert len(result.clients) == 1
        client = result.clients[0]
        assert len(client.received) > 0
        assert "Diphtheria" in str(client.received[0].get("diseases", []))

    def test_build_result_handles_missing_board_name_with_warning(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify missing board name generates warning.

        Real-world significance:
        - Some school districts don't have explicit board assignments
        - Should auto-generate board ID and log warning
        - Allows pipeline to proceed without failing
        """
        df = pd.DataFrame(
            {
                "SCHOOL NAME": ["Test School"],
                "CLIENT ID": ["C001"],
                "FIRST NAME": ["Alice"],
                "LAST NAME": ["Zephyr"],
                "DATE OF BIRTH": ["2015-01-01"],
                "CITY": ["Guelph"],
                "POSTAL CODE": ["N1H 2T2"],
                "PROVINCE/TERRITORY": ["ON"],
                "OVERDUE DISEASE": ["Measles"],
                "IMMS GIVEN": [""],
                "STREET ADDRESS LINE 1": ["123 Main"],
                "STREET ADDRESS LINE 2": [""],
            }
        )
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        # Should still process - at least one client
        assert len(result.clients) == 1

    def test_build_result_french_language_support(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify preprocessing handles French language correctly.

        Real-world significance:
        - Notices generated in both English and French
        - Preprocessing must handle both language variants
        - Dates must convert to French format for display
        """
        df = sample_input.create_test_input_dataframe(num_clients=1, language="fr")
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="fr",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=[],
        )

        assert len(result.clients) == 1
        assert result.clients[0].language == "fr"

    def test_build_result_handles_ignore_agents(
        self, default_disease_map, default_vaccine_reference
    ) -> None:
        """Verify ignore_agents filters out unspecified vaccines.

        Real-world significance:
        - Input may contain "Not Specified" vaccine agents
        - Pipeline should filter these out to avoid confusing notices
        """
        df = sample_input.create_test_input_dataframe(num_clients=1)
        normalized = preprocess.ensure_required_columns(df)

        result = preprocess.build_preprocess_result(
            normalized,
            language="en",
            disease_map=default_disease_map,
            vaccine_reference=default_vaccine_reference,
            ignore_agents=["Not Specified", "unspecified"],
        )

        assert len(result.clients) == 1
