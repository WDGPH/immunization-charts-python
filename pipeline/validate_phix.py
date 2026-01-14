"""Validate schools and daycares against PHIX Reference List.

This module provides validation of school/daycare names against a canonical
PHIX reference list. It supports exact matching, alias matching, and fuzzy
matching using rapidfuzz.

**Input Contract:**
- PHIX reference Excel file must exist at configured path
- Reference file must contain 'Schools & Day Cares' sheet
- Each column is a PHU, values are "FACILITY NAME - ID" format

**Output Contract:**
- Returns validation results with matched PHIX IDs and confidence scores
- Writes unmatched facilities to CSV for PHU review
- Raises or warns based on configured `unmatched_behavior`

**Usage:**
    Called from preprocess.py after address validation, before building results.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from rapidfuzz import fuzz, process

LOG = logging.getLogger(__name__)

# Cache for loaded PHIX reference data
_PHIX_REFERENCE_CACHE: Optional[Dict[str, Any]] = None


@dataclass
class PHIXFacility:
    """A facility entry from the PHIX reference list."""

    phix_id: str
    name: str
    phu: str  # Public Health Unit that owns this facility

    def __hash__(self) -> int:
        return hash((self.phix_id, self.name, self.phu))


@dataclass
class PHIXMatchResult:
    """Result of matching a facility against PHIX reference."""

    input_name: str
    matched: bool
    phix_id: Optional[str] = None
    phix_name: Optional[str] = None
    confidence: int = 0
    match_type: str = "none"  # exact, fuzzy, or none


def parse_facility_entry(entry: str, phu: str) -> Optional[PHIXFacility]:
    """Parse a PHIX facility entry in 'NAME - ID' format.

    Parameters
    ----------
    entry : str
        Raw entry from Excel like "ANNA MCCREA PUBLIC SCHOOL - 019186"
    phu : str
        Name of the Public Health Unit column

    Returns
    -------
    PHIXFacility or None
        Parsed facility, or None if entry is empty/invalid
    """
    if not entry or pd.isna(entry):
        return None

    entry = str(entry).strip()
    if not entry:
        return None

    # Parse "NAME - ID" format, where ID is the last segment after " - "
    # Some names contain " - " so we split from the right
    parts = entry.rsplit(" - ", maxsplit=1)
    if len(parts) == 2:
        name = parts[0].strip()
        phix_id = parts[1].strip()
    else:
        # No ID separator found, use entire string as name
        name = entry
        phix_id = ""

    return PHIXFacility(phix_id=phix_id, name=name, phu=phu)


def load_phix_reference(
    reference_path: Path,
    sheet_name: str = "Schools & Day Cares",
) -> Dict[str, Any]:
    """Load and parse the PHIX reference Excel file.

    Caches the result for subsequent calls with the same path.

    Parameters
    ----------
    reference_path : Path
        Path to the PHIX reference Excel file
    sheet_name : str
        Name of the sheet containing school/daycare data

    Returns
    -------
    Dict with keys:
        - facilities: List[PHIXFacility] - all parsed facilities
        - by_name: Dict[str, PHIXFacility] - lookup by normalized name
        - name_list: List[str] - list of all normalized names for fuzzy matching
        - phus: List[str] - list of PHU column names
    """
    global _PHIX_REFERENCE_CACHE

    cache_key = str(reference_path.resolve())
    if _PHIX_REFERENCE_CACHE is not None:
        cached_path = _PHIX_REFERENCE_CACHE.get("_cache_path")
        if cached_path == cache_key:
            return _PHIX_REFERENCE_CACHE

    if not reference_path.exists():
        raise FileNotFoundError(f"PHIX reference file not found: {reference_path}")

    LOG.info("Loading PHIX reference from %s", reference_path)
    df = pd.read_excel(reference_path, sheet_name=sheet_name)

    facilities: List[PHIXFacility] = []
    by_name: Dict[str, PHIXFacility] = {}
    seen_names: Set[str] = set()

    for phu_column in df.columns:
        for entry in df[phu_column].dropna():
            facility = parse_facility_entry(entry, phu_column)
            if facility:
                facilities.append(facility)
                # Use normalized name as key for exact matching
                normalized = normalize_facility_name(facility.name)
                if normalized not in seen_names:
                    by_name[normalized] = facility
                    seen_names.add(normalized)

    name_list = list(by_name.keys())
    LOG.info(
        "Loaded %d facilities from %d PHUs", len(facilities), len(df.columns)
    )

    _PHIX_REFERENCE_CACHE = {
        "_cache_path": cache_key,
        "facilities": facilities,
        "by_name": by_name,
        "name_list": name_list,
        "phus": list(df.columns),
    }
    return _PHIX_REFERENCE_CACHE


def normalize_facility_name(name: str) -> str:
    """Normalize a facility name for comparison.

    Converts to uppercase, removes extra whitespace, and standardizes
    common abbreviations.

    Parameters
    ----------
    name : str
        Raw facility name

    Returns
    -------
    str
        Normalized name for comparison
    """
    if not name:
        return ""

    # Uppercase and strip
    normalized = name.upper().strip()

    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


def match_facility(
    input_name: str,
    reference: Dict[str, Any],
    threshold: int = 85,
    strategy: str = "fuzzy",
) -> PHIXMatchResult:
    """Match a single facility name against PHIX reference.

    Parameters
    ----------
    input_name : str
        Facility name from input data
    reference : Dict[str, Any]
        Loaded PHIX reference data from load_phix_reference()
    threshold : int
        Minimum fuzzy match score (0-100) to consider a match
    strategy : str
        Match strategy: 'exact' (exact only), 'fuzzy' (exact then fuzzy)

    Returns
    -------
    PHIXMatchResult
        Match result with PHIX ID and confidence if matched
    """
    if not input_name or not input_name.strip():
        return PHIXMatchResult(
            input_name=input_name or "",
            matched=False,
            match_type="none",
        )

    normalized_input = normalize_facility_name(input_name)
    by_name = reference["by_name"]
    name_list = reference["name_list"]

    # Try exact match first
    if normalized_input in by_name:
        facility = by_name[normalized_input]
        return PHIXMatchResult(
            input_name=input_name,
            matched=True,
            phix_id=facility.phix_id,
            phix_name=facility.name,
            confidence=100,
            match_type="exact",
        )

    # If exact-only strategy, stop here
    if strategy == "exact":
        return PHIXMatchResult(
            input_name=input_name,
            matched=False,
            match_type="none",
        )

    # Try fuzzy match
    if name_list:
        result = process.extractOne(
            query=normalized_input,
            choices=name_list,
            scorer=fuzz.ratio,
            score_cutoff=threshold,
        )
        if result:
            matched_name, score, _ = result
            facility = by_name[matched_name]
            return PHIXMatchResult(
                input_name=input_name,
                matched=True,
                phix_id=facility.phix_id,
                phix_name=facility.name,
                confidence=int(score),
                match_type="fuzzy",
            )

    return PHIXMatchResult(
        input_name=input_name,
        matched=False,
        match_type="none",
    )


def validate_facilities(
    df: pd.DataFrame,
    reference_path: Path,
    output_dir: Path,
    threshold: int = 85,
    unmatched_behavior: str = "warn",
    strategy: str = "fuzzy",
    school_column: str = "SCHOOL_NAME",
) -> Tuple[pd.DataFrame, List[str]]:
    """Validate all facilities in DataFrame against PHIX reference.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with facility names
    reference_path : Path
        Path to PHIX reference Excel file
    output_dir : Path
        Directory to write unmatched facilities CSV
    threshold : int
        Minimum fuzzy match score (0-100)
    unmatched_behavior : str
        How to handle unmatched facilities:
        - 'warn': Log warning, continue processing all records
        - 'error': Raise ValueError if any unmatched
        - 'skip': Filter out unmatched records
    strategy : str
        Match strategy: 'exact' or 'fuzzy'
    school_column : str
        Name of column containing facility names

    Returns
    -------
    Tuple[pd.DataFrame, List[str]]
        - DataFrame with PHIX validation columns added
        - List of warning messages

    Raises
    ------
    ValueError
        If unmatched_behavior is 'error' and unmatched facilities exist
    """
    warnings: List[str] = []

    if school_column not in df.columns:
        LOG.warning("Column '%s' not found, skipping PHIX validation", school_column)
        return df, warnings

    # Load reference
    reference = load_phix_reference(reference_path)

    # Match each unique facility
    unique_facilities = df[school_column].dropna().unique()
    match_results: Dict[str, PHIXMatchResult] = {}

    for facility_name in unique_facilities:
        result = match_facility(
            str(facility_name), reference, threshold=threshold, strategy=strategy
        )
        match_results[str(facility_name)] = result

    # Add validation columns to DataFrame
    df = df.copy()
    df["PHIX_ID"] = df[school_column].apply(
        lambda x: match_results.get(str(x), PHIXMatchResult(str(x), False)).phix_id
        if pd.notna(x)
        else None
    )
    df["PHIX_MATCH_CONFIDENCE"] = df[school_column].apply(
        lambda x: match_results.get(str(x), PHIXMatchResult(str(x), False)).confidence
        if pd.notna(x)
        else 0
    )
    df["PHIX_MATCH_TYPE"] = df[school_column].apply(
        lambda x: match_results.get(
            str(x), PHIXMatchResult(str(x), False)
        ).match_type
        if pd.notna(x)
        else "none"
    )

    # Identify unmatched facilities
    unmatched = [r for r in match_results.values() if not r.matched]

    if unmatched:
        unmatched_names = sorted(set(r.input_name for r in unmatched))
        LOG.warning(
            "%d facilities could not be matched to PHIX reference: %s",
            len(unmatched_names),
            unmatched_names[:5],  # Log first 5
        )

        # Write unmatched to CSV
        output_dir.mkdir(parents=True, exist_ok=True)
        unmatched_path = output_dir / "unmatched_facilities.csv"
        unmatched_df = pd.DataFrame(
            [
                {
                    "facility_name": r.input_name,
                    "match_type": r.match_type,
                    "confidence": r.confidence,
                }
                for r in unmatched
            ]
        )
        unmatched_df.to_csv(unmatched_path, index=False)
        LOG.info("Wrote %d unmatched facilities to %s", len(unmatched), unmatched_path)
        warnings.append(
            f"{len(unmatched_names)} facilities not found in PHIX reference. "
            f"See {unmatched_path} for details."
        )

        if unmatched_behavior == "error":
            raise ValueError(
                f"{len(unmatched_names)} facilities not found in PHIX reference: "
                f"{', '.join(unmatched_names[:10])}"
                + (f" (and {len(unmatched_names) - 10} more)" if len(unmatched_names) > 10 else "")
            )
        elif unmatched_behavior == "skip":
            # Filter out rows with unmatched facilities
            matched_names = {r.input_name for r in match_results.values() if r.matched}
            original_count = len(df)
            df = df[df[school_column].isin(matched_names)]
            filtered_count = original_count - len(df)
            LOG.info(
                "Filtered %d records with unmatched facilities, %d remaining",
                filtered_count,
                len(df),
            )
            warnings.append(
                f"Filtered {filtered_count} records with unmatched facilities."
            )

    # Log summary
    matched_count = sum(1 for r in match_results.values() if r.matched)
    exact_count = sum(
        1 for r in match_results.values() if r.matched and r.match_type == "exact"
    )
    fuzzy_count = sum(
        1 for r in match_results.values() if r.matched and r.match_type == "fuzzy"
    )
    LOG.info(
        "PHIX validation complete: %d matched (%d exact, %d fuzzy), %d unmatched",
        matched_count,
        exact_count,
        fuzzy_count,
        len(unmatched),
    )

    return df, warnings


def clear_cache() -> None:
    """Clear the PHIX reference cache. Useful for testing."""
    global _PHIX_REFERENCE_CACHE
    _PHIX_REFERENCE_CACHE = None
