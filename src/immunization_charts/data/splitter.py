"""
Data splitting utilities for immunization charts.

This module provides functions for splitting data by school and creating batches
for processing immunization data in manageable chunks.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ..utils.file_utils import ensure_directory, get_safe_filename

logger = logging.getLogger(__name__)


def separate_by_column(data: pd.DataFrame, col_name: str, out_path: Path) -> None:
    """Group a DataFrame by a column and save each group to a separate CSV.

    Args:
        data: DataFrame to separate
        col_name: Column name to group by
        out_path: Output directory for separated files

    Raises:
        ValueError: If column doesn't exist in DataFrame
    """
    ensure_directory(out_path)

    if col_name not in data.columns:
        raise ValueError(f"Column {col_name} not found in DataFrame")

    grouped = data.groupby(col_name)

    for name, group in grouped:
        safe_name = get_safe_filename(name)
        output_file = out_path / f"{safe_name}.csv"

        logger.info(f"Processing group: {safe_name}")
        group.to_csv(output_file, index=False, sep=";")
        logger.info(f"Saved group {safe_name} with {len(group)} rows to {output_file}")


def split_batches(input_dir: Path, output_dir: Path, batch_size: int) -> None:
    """Split CSV files in input_dir into batches of size batch_size.

    Args:
        input_dir: Directory containing CSV files to split
        output_dir: Directory to save batch files
        batch_size: Number of rows per batch
    """
    ensure_directory(output_dir)

    csv_files = list(input_dir.glob("*.csv"))

    if not csv_files:
        logger.warning(f"No CSV files found in {input_dir}")
        return

    for file in csv_files:
        df = pd.read_csv(
            file, sep=";", engine="python", encoding="latin-1", quotechar='"'
        )
        filename_base = file.stem

        # Split into batches
        num_batches = (len(df) + batch_size - 1) // batch_size  # ceiling division
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size
            batch_df = df.iloc[start_idx:end_idx]

            batch_file = output_dir / f"{filename_base}_{i+1:02d}.csv"
            batch_df.to_csv(batch_file, index=False, sep=";")
            logger.info(f"Saved batch: {batch_file} ({len(batch_df)} rows)")


def separate_by_school(
    df: pd.DataFrame, output_dir: str, school_column: str = "SCHOOL_NAME"
) -> None:
    """Separate the DataFrame by school/daycare and write separate CSVs.

    Args:
        df: Cleaned DataFrame
        output_dir: Path to directory where CSVs will be saved
        school_column: Column to separate by (default "SCHOOL_NAME")
    """
    output_path = Path(output_dir)

    logger.info(f"Separating data by {school_column}...")
    separate_by_column(df, school_column, output_path)
    logger.info(f"Data separated by {school_column}. Files saved to {output_path}.")


def process_batch_files(
    batch_dir: Path, output_dir: Path, language: str = "english"
) -> None:
    """Process all batch files in a directory.

    Args:
        batch_dir: Directory containing batch CSV files
        output_dir: Output directory for processed files
        language: Language for processing ("english" or "french")
    """
    all_batch_files = sorted(batch_dir.glob("*.csv"))

    if not all_batch_files:
        logger.warning(f"No batch files found in {batch_dir}")
        return

    for batch_file in all_batch_files:
        logger.info(f"Processing batch file: {batch_file}")
        df_batch = pd.read_csv(
            batch_file, sep=";", engine="python", encoding="latin-1", quotechar='"'
        )

        # Combine address fields if they exist
        if "STREET_ADDRESS_LINE_2" in df_batch.columns:
            df_batch["STREET_ADDRESS"] = (
                df_batch["STREET_ADDRESS_LINE_1"].fillna("")
                + " "
                + df_batch["STREET_ADDRESS_LINE_2"].fillna("")
            )
            df_batch.drop(
                columns=["STREET_ADDRESS_LINE_1", "STREET_ADDRESS_LINE_2"], inplace=True
            )

        # Process the batch (this would call the processor)
        logger.info(f"Processed batch: {batch_file.stem}")
