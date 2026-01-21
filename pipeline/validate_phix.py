"""Validate schools and daycares against PHIX Reference List.

This module provides validation of school/daycare names against a canonical
PHIX reference list. It supports strict exact matching plus PHU alias
scoping to prevent cross-jurisdiction matches.

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
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd
import yaml

LOG = logging.getLogger(__name__)

# Cache for loaded PHIX reference data and PHU alias mappings
_PHIX_REFERENCE_CACHE: Optional[Dict[str, Any]] = None
_PHU_MAPPING_CACHE: Optional[Dict[str, Any]] = None


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
    phu_name: Optional[str] = None
    phu_code: Optional[str] = None
    confidence: int = 0
    match_type: str = "none"  # exact or none


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
        - by_name_phu: Dict[str, Dict[str, PHIXFacility]] - lookup by PHU column
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
    by_name_phu: Dict[str, Dict[str, PHIXFacility]] = {}
    seen_names: Set[str] = set()

    for phu_column in df.columns:
        for entry in df[phu_column].dropna():
            facility = parse_facility_entry(entry, phu_column)
            if facility:
                facilities.append(facility)
                # Use normalized name as key for exact matching
                normalized = normalize_facility_name(facility.name)
                by_name_phu.setdefault(normalized, {})[phu_column] = facility
                if normalized not in seen_names:
                    by_name[normalized] = facility
                    seen_names.add(normalized)

    LOG.info(
        "Loaded %d facilities from %d PHUs", len(facilities), len(df.columns)
    )

    _PHIX_REFERENCE_CACHE = {
        "_cache_path": cache_key,
        "facilities": facilities,
        "by_name": by_name,
        "by_name_phu": by_name_phu,
        "phus": list(df.columns),
    }
    return _PHIX_REFERENCE_CACHE


def normalize_phu_code(code: str) -> str:
    """Normalize a PHU acronym/template key for comparison."""
    if not code:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "_", code.strip().lower())
    return normalized.strip("_")


def normalize_phu_label(label: str) -> str:
    """Normalize PHU names/aliases for lookup."""
    if not label:
        return ""
    return re.sub(r"\s+", " ", str(label).strip().upper())


def load_phu_aliases(mapping_path: Path) -> Dict[str, Any]:
    """Load canonical PHU aliases from YAML mapping file."""
    global _PHU_MAPPING_CACHE

    cache_key = str(mapping_path.resolve())
    if _PHU_MAPPING_CACHE is not None:
        cached_path = _PHU_MAPPING_CACHE.get("_cache_path")
        if cached_path == cache_key:
            return _PHU_MAPPING_CACHE

    if not mapping_path.exists():
        raise FileNotFoundError(f"PHU alias mapping file not found: {mapping_path}")

    raw = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("phu_aliases")
    if not isinstance(entries, dict):
        raise ValueError(
            f"Invalid PHU alias mapping format in {mapping_path}. "
            "Expected top-level 'phu_aliases' dictionary."
        )

    alias_to_code: Dict[str, str] = {}
    code_to_display: Dict[str, str] = {}
    code_to_aliases: Dict[str, Set[str]] = {}

    for code, meta in entries.items():
        normalized_code = normalize_phu_code(code)
        if not normalized_code:
            continue

        meta = meta or {}
        display_name = str(meta.get("display_name") or code).strip()
        code_to_display[normalized_code] = display_name

        aliases = meta.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]

        alias_candidates = set(
            filter(
                None,
                [
                    *[str(alias) for alias in aliases],
                    code,
                    display_name,
                ],
            )
        )

        for alias in alias_candidates:
            normalized_alias = normalize_phu_label(alias)
            if not normalized_alias:
                continue
            alias_to_code[normalized_alias] = normalized_code
            code_to_aliases.setdefault(normalized_code, set()).add(str(alias).strip())

    _PHU_MAPPING_CACHE = {
        "_cache_path": cache_key,
        "alias_to_code": alias_to_code,
        "code_to_display": code_to_display,
        "code_to_aliases": code_to_aliases,
    }
    return _PHU_MAPPING_CACHE


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
    facility_phu_codes: Optional[Dict[str, Optional[str]]] = None,
) -> PHIXMatchResult:
    """Match a single facility name against PHIX reference using exact match."""
    if not input_name or not input_name.strip():
        return PHIXMatchResult(
            input_name=input_name or "",
            matched=False,
            match_type="none",
        )

    normalized_input = normalize_facility_name(input_name)
    by_name = reference["by_name"]

    # Try exact match first
    if normalized_input in by_name:
        facility = by_name[normalized_input]
        phu_code = facility_phu_codes.get(normalized_input) if facility_phu_codes else None
        return PHIXMatchResult(
            input_name=input_name,
            matched=True,
            phix_id=facility.phix_id,
            phix_name=facility.name,
            phu_name=facility.phu,
            phu_code=phu_code,
            confidence=100,
            match_type="exact",
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
    unmatched_behavior: str = "warn",
    school_column: str = "SCHOOL_NAME",
    target_phu_codes: Optional[Iterable[str]] = None,
    phu_mapping_path: Optional[Path] = None,
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
    unmatched_behavior : str
        How to handle unmatched facilities:
        - 'warn': Log warning, continue processing all records
        - 'error': Raise ValueError if any unmatched
        - 'skip': Filter out unmatched records
    school_column : str
        Name of column containing facility names
    target_phu_codes : Iterable[str], optional
        Canonical PHU codes (matching template folders) to restrict validation.
        When provided, only facilities that belong to these PHUs are considered.
    phu_mapping_path : Path, optional
        Path to YAML mapping file that links PHIX column names to canonical PHU
        codes. Required when target_phu_codes are provided.

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

    phu_mapping_data: Optional[Dict[str, Any]] = None
    alias_lookup: Dict[str, str] = {}
    if phu_mapping_path:
        phu_mapping_data = load_phu_aliases(phu_mapping_path)
        alias_lookup = phu_mapping_data.get("alias_to_code", {})

    normalized_target_codes: Set[str] = set()
    if target_phu_codes:
        for code in target_phu_codes:
            normalized = normalize_phu_code(code)
            if normalized:
                normalized_target_codes.add(normalized)
        if normalized_target_codes and not phu_mapping_data:
            raise ValueError(
                "Target PHU codes provided but phu_mapping_file is not configured. "
                "Update phix_validation.phu_mapping_file to scope validation."
            )

    if normalized_target_codes and phu_mapping_data:
        code_to_display = phu_mapping_data.get("code_to_display", {})
        missing_codes = sorted(
            code for code in normalized_target_codes if code not in code_to_display
        )
        if missing_codes:
            raise ValueError(
                f"Template PHU codes not defined in {phu_mapping_path}: "
                f"{', '.join(missing_codes)}. Update config/phu_aliases.yaml."
            )

    phu_column_codes: Dict[str, str] = {}
    if alias_lookup:
        for phu_column in reference["phus"]:
            canonical_code = alias_lookup.get(normalize_phu_label(phu_column))
            if canonical_code:
                phu_column_codes[phu_column] = canonical_code

    reference_for_matching = reference
    target_display: Optional[str] = None
    target_codes_str: Optional[str] = None

    if normalized_target_codes:
        allowed_phu_columns = [
            column
            for column, code in phu_column_codes.items()
            if code in normalized_target_codes
        ]
        if not allowed_phu_columns:
            raise ValueError(
                "No PHIX columns mapped to the requested PHU codes. "
                f"Template codes: {', '.join(sorted(normalized_target_codes))}. "
                "Confirm config/phu_aliases.yaml contains the PHIX column names."
            )

        by_name_phu: Dict[str, Dict[str, PHIXFacility]] = reference.get(
            "by_name_phu", {}
        )
        filtered_by_name: Dict[str, PHIXFacility] = {}
        filtered_name_list: List[str] = []
        for normalized_name, facilities_by_phu in by_name_phu.items():
            for phu_label in allowed_phu_columns:
                facility = facilities_by_phu.get(phu_label)
                if facility:
                    filtered_by_name[normalized_name] = facility
                    filtered_name_list.append(normalized_name)
                    break

        if not filtered_by_name:
            raise ValueError(
                "No PHIX reference entries found for the requested PHU columns. "
                f"Columns: {', '.join(sorted(allowed_phu_columns))}. "
                "Verify the mapping file includes every PHIX alias."
            )

        reference_for_matching = dict(reference)
        reference_for_matching["by_name"] = filtered_by_name
        reference_for_matching["name_list"] = filtered_name_list

        code_to_display = phu_mapping_data.get("code_to_display", {}) if phu_mapping_data else {}
        target_display = ", ".join(
            code_to_display.get(code, code).strip() for code in sorted(normalized_target_codes)
        )
        target_codes_str = ",".join(sorted(normalized_target_codes))
        LOG.info(
            "Restricting PHIX validation to PHU(s): %s",
            target_display or target_codes_str,
        )

    facility_phu_codes_for_matching: Dict[str, Optional[str]] = {}
    if alias_lookup:
        for normalized_name, facility in reference_for_matching["by_name"].items():
            canonical_code = alias_lookup.get(normalize_phu_label(facility.phu))
            if canonical_code:
                facility_phu_codes_for_matching[normalized_name] = canonical_code

    # Match each unique facility
    unique_facilities = df[school_column].dropna().unique()
    match_results: Dict[str, PHIXMatchResult] = {}

    for facility_name in unique_facilities:
        result = match_facility(
            str(facility_name),
            reference_for_matching,
            facility_phu_codes=(
                facility_phu_codes_for_matching
                if facility_phu_codes_for_matching
                else None
            ),
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
    df["PHIX_MATCHED_PHU"] = df[school_column].apply(
        lambda x: match_results.get(
            str(x), PHIXMatchResult(str(x), False)
        ).phu_name
        if pd.notna(x)
        else None
    )
    df["PHIX_MATCHED_PHU_CODE"] = df[school_column].apply(
        lambda x: match_results.get(
            str(x), PHIXMatchResult(str(x), False)
        ).phu_code
        if pd.notna(x)
        else None
    )
    df["PHIX_TARGET_PHU_CODE"] = target_codes_str
    df["PHIX_TARGET_PHU_LABEL"] = target_display

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
                    "target_phu_code": target_codes_str or "",
                    "target_phu_label": target_display or "",
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
    LOG.info(
        "PHIX validation complete: %d matched, %d unmatched",
        matched_count,
        len(unmatched),
    )

    return df, warnings


def clear_cache() -> None:
    """Clear the PHIX reference cache. Useful for testing."""
    global _PHIX_REFERENCE_CACHE, _PHU_MAPPING_CACHE
    _PHIX_REFERENCE_CACHE = None
    _PHU_MAPPING_CACHE = None
