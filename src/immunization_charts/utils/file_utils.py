"""
File utility functions for immunization charts.

This module provides file operations and validation utilities
for handling input/output files in the immunization system.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def detect_file_type(file_path: Path) -> str:
    """Return the file extension for preprocessing logic.

    Args:
        file_path: Path to the file to check

    Returns:
        File extension in lowercase

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    return file_path.suffix.lower()


def check_file_existence(file_path: Path) -> bool:
    """Check if a file exists and is accessible.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file exists and is accessible, False otherwise
    """
    exists = file_path.exists() and file_path.is_file()
    if exists:
        logger.info(f"File exists: {file_path}")
    else:
        logger.warning(f"File does not exist: {file_path}")
    return exists


def ensure_directory(directory_path: Path) -> None:
    """Ensure a directory exists, creating it if necessary.

    Args:
        directory_path: Path to the directory to ensure exists
    """
    directory_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured directory exists: {directory_path}")


def get_safe_filename(name: str) -> str:
    """Convert a name to a safe filename by replacing problematic characters.

    Args:
        name: Original name to convert

    Returns:
        Safe filename with problematic characters replaced
    """
    return (
        str(name)
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "")
        .upper()
    )


def list_files_with_extension(directory: Path, extension: str) -> list[Path]:
    """List all files with a specific extension in a directory.

    Args:
        directory: Directory to search in
        extension: File extension to search for (e.g., '.csv', '.json')

    Returns:
        List of Path objects for matching files
    """
    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    files = list(directory.glob(f"*{extension}"))
    logger.info(f"Found {len(files)} {extension} files in {directory}")
    return files
