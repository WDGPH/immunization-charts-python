"""
Tests for the ClientDataProcessor class.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.immunization_charts.core.processor import ClientDataProcessor


class TestClientDataProcessor:
    """Test cases for ClientDataProcessor."""

    def test_initialization(self):
        """Test processor initialization."""
        df = pd.DataFrame(
            {
                "CLIENT_ID": ["123"],
                "FIRST_NAME": ["John"],
                "LAST_NAME": ["Doe"],
                "SCHOOL_NAME": ["Test School"],
                "DATE_OF_BIRTH": ["2010-01-01"],
                "STREET_ADDRESS": ["123 Main St"],
                "CITY": ["Test City"],
                "POSTAL_CODE": ["A1A 1A1"],
                "PROVINCE": ["ON"],
                "AGE": [14],
                "OVERDUE_DISEASE": ["Measles"],
                "IMMS_GIVEN": ["Jan 1, 2020 - MMR"],
            }
        )

        processor = ClientDataProcessor(df, language="english")

        assert processor.language == "english"
        assert len(processor.df) == 1
        assert len(processor.notices) == 0  # Notices built after build_notices()

    def test_process_vaccines_due_english(self):
        """Test vaccine due processing in English."""
        df = pd.DataFrame(
            {
                "CLIENT_ID": ["123"],
                "FIRST_NAME": ["John"],
                "LAST_NAME": ["Doe"],
                "SCHOOL_NAME": ["Test School"],
                "DATE_OF_BIRTH": ["2010-01-01"],
                "STREET_ADDRESS": ["123 Main St"],
                "CITY": ["Test City"],
                "POSTAL_CODE": ["A1A 1A1"],
                "PROVINCE": ["ON"],
                "AGE": [14],
                "OVERDUE_DISEASE": ["Measles, Polio"],
                "IMMS_GIVEN": ["Jan 1, 2020 - MMR"],
            }
        )

        processor = ClientDataProcessor(df, language="english")
        result = processor.process_vaccines_due("Measles, Polio")

        assert "Measles" in result
        assert "Polio" in result

    def test_process_vaccines_due_french(self):
        """Test vaccine due processing in French."""
        df = pd.DataFrame(
            {
                "CLIENT_ID": ["123"],
                "FIRST_NAME": ["John"],
                "LAST_NAME": ["Doe"],
                "SCHOOL_NAME": ["Test School"],
                "DATE_OF_BIRTH": ["2010-01-01"],
                "STREET_ADDRESS": ["123 Main St"],
                "CITY": ["Test City"],
                "POSTAL_CODE": ["A1A 1A1"],
                "PROVINCE": ["ON"],
                "AGE": [14],
                "OVERDUE_DISEASE": ["Rougeole"],
                "IMMS_GIVEN": ["Jan 1, 2020 - ROR"],
            }
        )

        processor = ClientDataProcessor(df, language="french")
        result = processor.process_vaccines_due("Rougeole")

        assert "Rougeole" in result

    def test_process_received_agents(self):
        """Test processing of received vaccination agents."""
        df = pd.DataFrame(
            {
                "CLIENT_ID": ["123"],
                "FIRST_NAME": ["John"],
                "LAST_NAME": ["Doe"],
                "SCHOOL_NAME": ["Test School"],
                "DATE_OF_BIRTH": ["2010-01-01"],
                "STREET_ADDRESS": ["123 Main St"],
                "CITY": ["Test City"],
                "POSTAL_CODE": ["A1A 1A1"],
                "PROVINCE": ["ON"],
                "AGE": [14],
                "OVERDUE_DISEASE": ["Measles"],
                "IMMS_GIVEN": ["Jan 1, 2020 - MMR, Feb 1, 2020 - DTaP"],
            }
        )

        processor = ClientDataProcessor(df, language="english")
        result = processor.process_received_agents(
            "Jan 1, 2020 - MMR, Feb 1, 2020 - DTaP"
        )

        assert len(result) == 2
        assert result[0][0] == "2020-01-01"  # Date
        assert result[0][1] == "MMR"  # Vaccine
        assert result[1][0] == "2020-02-01"  # Date
        assert result[1][1] == "DTaP"  # Vaccine

    def test_build_notices(self):
        """Test building notices for clients."""
        df = pd.DataFrame(
            {
                "CLIENT_ID": ["123"],
                "FIRST_NAME": ["John"],
                "LAST_NAME": ["Doe"],
                "SCHOOL_NAME": ["Test School"],
                "DATE_OF_BIRTH": ["2010-01-01"],
                "STREET_ADDRESS": ["123 Main St"],
                "CITY": ["Test City"],
                "POSTAL_CODE": ["A1A 1A1"],
                "PROVINCE": ["ON"],
                "AGE": [14],
                "OVERDUE_DISEASE": ["Measles"],
                "IMMS_GIVEN": ["Jan 1, 2020 - MMR"],
            }
        )

        processor = ClientDataProcessor(df, language="english")
        processor.build_notices()

        notices = processor.get_notices()
        assert "123" in notices
        assert notices["123"]["name"] == "John Doe"
        assert notices["123"]["school"] == "Test School"
        assert notices["123"]["over_16"] == False  # Age 14
        assert len(notices["123"]["received"]) == 1
