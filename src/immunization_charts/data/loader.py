"""
Data loading utilities for immunization charts.

This module provides functions for loading and validating input data
from various file formats (CSV, Excel) used in the immunization system.
"""

import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

from ..utils.file_utils import detect_file_type

logger = logging.getLogger(__name__)


def read_input(file_path: Path) -> pd.DataFrame:
    """Read CSV/Excel into DataFrame with robust encoding and delimiter detection.

    Args:
        file_path: Path to the input file

    Returns:
        Loaded DataFrame

    Raises:
        ValueError: If file type is unsupported
        FileNotFoundError: If file doesn't exist
    """
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
                raise ValueError(
                    "Could not decode CSV with common encodings or delimiters"
                )
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        logger.info(f"Loaded {len(df)} rows from {file_path}")
        return df

    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        raise


def load_data(input_file: str) -> pd.DataFrame:
    """Load and clean data from input file.

    Args:
        input_file: Path to the input file

    Returns:
        Cleaned DataFrame with normalized column names
    """
    df = read_input(Path(input_file))

    # Replace column names with uppercase
    df.columns = [col.strip().upper() for col in df.columns]
    logger.info(f"Columns after loading: {df.columns.tolist()}")

    return df


def validate_columns(df: pd.DataFrame, required_columns: List[str]) -> None:
    """Validate that required columns are present in the DataFrame.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names

    Raises:
        ValueError: If required columns are missing
    """
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols} "
            f"in DataFrame with columns {df.columns.tolist()}"
        )

    logger.info("All required columns are present.")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names in the DataFrame.

    Args:
        df: DataFrame to normalize

    Returns:
        DataFrame with normalized column names
    """
    # Rename columns to have underscores instead of spaces
    df = df.rename(columns=lambda x: x.replace(" ", "_"))

    # Rename PROVINCE/TERRITORY to PROVINCE
    df = df.rename(columns={"PROVINCE/TERRITORY": "PROVINCE"})

    logger.info("Column names normalized.")
    return df


def load_and_validate_data(
    input_file: str, required_columns: List[str]
) -> pd.DataFrame:
    """Load data and validate required columns.

    Args:
        input_file: Path to the input file
        required_columns: List of required column names

    Returns:
        Loaded and validated DataFrame
    """
    df = load_data(input_file)
    df = normalize_columns(df)
    validate_columns(df, required_columns)
    return df
