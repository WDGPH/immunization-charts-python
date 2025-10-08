"""
PDF utility functions for immunization charts.

This module provides PDF processing utilities for handling
generated PDF files in the immunization system.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

logger = logging.getLogger(__name__)


def count_pdf_pages(pdf_file: Path) -> Optional[int]:
    """Count the number of pages in a PDF file.

    Args:
        pdf_file: Path to the PDF file

    Returns:
        Number of pages in the PDF, or None if error occurred
    """
    if PdfReader is None:
        logger.error("PyPDF2 is not installed. Cannot process PDF files.")
        return None

    try:
        reader = PdfReader(pdf_file)
        num_pages = len(reader.pages)
        logger.info(f"PDF '{pdf_file}' has {num_pages} pages.")
        return num_pages
    except Exception as e:
        logger.error(f"Error reading PDF '{pdf_file}': {e}")
        return None


def validate_pdf_file(pdf_file: Path) -> bool:
    """Validate that a PDF file is readable and not corrupted.

    Args:
        pdf_file: Path to the PDF file to validate

    Returns:
        True if PDF is valid and readable, False otherwise
    """
    if not pdf_file.exists():
        logger.error(f"PDF file does not exist: {pdf_file}")
        return False

    if not pdf_file.suffix.lower() == ".pdf":
        logger.error(f"File is not a PDF: {pdf_file}")
        return False

    page_count = count_pdf_pages(pdf_file)
    return page_count is not None and page_count > 0


def get_pdf_info(pdf_file: Path) -> dict:
    """Get information about a PDF file.

    Args:
        pdf_file: Path to the PDF file

    Returns:
        Dictionary containing PDF information
    """
    info = {
        "file_path": str(pdf_file),
        "exists": pdf_file.exists(),
        "size_bytes": pdf_file.stat().st_size if pdf_file.exists() else 0,
        "page_count": None,
        "is_valid": False,
    }

    if info["exists"]:
        info["page_count"] = count_pdf_pages(pdf_file)
        info["is_valid"] = info["page_count"] is not None and info["page_count"] > 0

    return info
