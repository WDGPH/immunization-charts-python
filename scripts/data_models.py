"""Unified data models for the immunization pipeline.

This module provides all core dataclasses used throughout the pipeline,
ensuring consistency and type safety across processing steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ClientRecord:
    """Unified client record across all pipeline steps.

    Fields:
    - person: Dict with full_name, date_of_birth, date_of_birth_display, date_of_birth_iso, age, over_16
    - school: Dict with name, code (optional)
    - board: Dict with name, code (optional)
    - contact: Dict with street, city, province, postal_code
    - qr: Optional Dict with payload, filename, path (optional)
    - metadata: Custom metadata dict
    - received: List of vaccine records received
    """

    sequence: str
    client_id: str
    language: str
    person: Dict[str, Any]
    school: Dict[str, Any]
    board: Dict[str, Any]
    contact: Dict[str, Any]
    vaccines_due: Optional[str]
    vaccines_due_list: Optional[List[str]]
    received: Optional[Sequence[Dict[str, object]]]
    metadata: Dict[str, object]
    qr: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class PreprocessResult:
    """Result of preprocessing step."""

    clients: List[ClientRecord]
    warnings: List[str]


@dataclass(frozen=True)
class ArtifactPayload:
    """Preprocessed artifact with metadata."""

    run_id: str
    language: str
    clients: List[ClientRecord]
    warnings: List[str]
    created_at: str
    input_file: Optional[str] = None
    total_clients: int = 0


@dataclass(frozen=True)
class PdfRecord:
    """Compiled PDF with client metadata."""

    sequence: str
    client_id: str
    pdf_path: Path
    page_count: int
    client: Dict[str, Any]
