"""Utility functions for immunization pipeline processing.

Provides template rendering utilities and context building functions shared
across pipeline steps, particularly for QR code generation, PDF encryption,
and template variable substitution. All functions handle string conversions
and safe formatting of client data for use in downstream templates."""

from __future__ import annotations

from string import Formatter
from typing import Any

# Template formatter for extracting field names from format strings
_FORMATTER = Formatter()


def string_or_empty(value: Any) -> str:
    """Safely convert value to string, returning empty string for None/NaN.

    Parameters
    ----------
    value : Any
        Value to convert (may be None, empty string, or any type)

    Returns
    -------
    str
        Stringified value or empty string for None/NaN values
    """
    if value is None:
        return ""
    return str(value).strip()


def extract_template_fields(template: str) -> set[str]:
    """Extract placeholder names from a format string template.

    Parameters
    ----------
    template : str
        Format string like "https://example.com?id={client_id}&dob={date_of_birth_iso}"

    Returns
    -------
    set[str]
        Set of placeholder names found in template

    Raises
    ------
    ValueError
        If template contains invalid format string syntax

    Examples
    --------
    >>> extract_template_fields("{client_id}_{date_of_birth_iso}")
    {'client_id', 'date_of_birth_iso'}
    """
    try:
        return {
            field_name
            for _, field_name, _, _ in _FORMATTER.parse(template)
            if field_name
        }
    except ValueError as exc:
        raise ValueError(f"Invalid template format: {exc}") from exc


def validate_and_format_template(
    template: str,
    context: dict[str, str],
    allowed_fields: set[str] | None = None,
) -> str:
    """Format template and validate placeholders against allowed set.

    Ensures that:
    1. All placeholders in template exist in context
    2. All placeholders are in the allowed_fields set (if provided)
    3. Template is successfully rendered

    Parameters
    ----------
    template : str
        Format string template with placeholders
    context : dict[str, str]
        Context dict with placeholder values
    allowed_fields : set[str] | None
        Set of allowed placeholder names. If None, allows any placeholder
        that exists in context.

    Returns
    -------
    str
        Rendered template

    Raises
    ------
    KeyError
        If template contains placeholders not in context
    ValueError
        If template contains disallowed placeholders (when allowed_fields provided)

    Examples
    --------
    >>> ctx = {"client_id": "12345", "date_of_birth_iso": "2015-03-15"}
    >>> validate_and_format_template(
    ...     "{client_id}_{date_of_birth_iso}",
    ...     ctx,
    ...     allowed_fields={"client_id", "date_of_birth_iso"}
    ... )
    '12345_2015-03-15'
    """
    placeholders = extract_template_fields(template)

    # Check for missing placeholders in context
    unknown_fields = placeholders - context.keys()
    if unknown_fields:
        raise KeyError(
            f"Unknown placeholder(s) {sorted(unknown_fields)} in template. "
            f"Available: {sorted(context.keys())}"
        )

    # Check for disallowed placeholders (if whitelist provided)
    if allowed_fields is not None:
        disallowed = placeholders - allowed_fields
        if disallowed:
            raise ValueError(
                f"Disallowed placeholder(s) {sorted(disallowed)} in template. "
                f"Allowed: {sorted(allowed_fields)}"
            )

    return template.format(**context)


def build_client_context(
    client_data: dict,
    language: str,
    date_notice_delivery: str | None = None,
) -> dict[str, str]:
    """Build template context dict from client metadata for templating.

    Extracts and formats all available client fields for use in templates,
    supporting both QR code payloads and PDF encryption passwords.

    Parameters
    ----------
    client_data : dict
        Client dict (from preprocessed artifact) with nested structure:
        {
            "client_id": "...",
            "person": {"full_name": "...", "date_of_birth_iso": "..."},
            "school": {"name": "..."},
            "board": {"name": "..."},
            "contact": {"postal_code": "...", "city": "...", ...}
        }
    language : str
        ISO 639-1 language code ('en' for English, 'fr' for French). Must be a valid
        Language enum value (see pipeline.enums.Language). Validated using
        Language.from_string() at entry points; this function assumes language is valid.
    date_notice_delivery : str | None
        Optional notice delivery date for template rendering

    Returns
    -------
    dict[str, str]
        Context dict with keys:
        - client_id
        - first_name, last_name, name
        - date_of_birth (display format)
        - date_of_birth_iso (YYYY-MM-DD)
        - date_of_birth_iso_compact (YYYYMMDD)
        - school, board
        - postal_code, city, province, street_address
        - language_code ('en' or 'fr')
        - date_notice_delivery (if provided)

    Examples
    --------
    >>> client = {
    ...     "client_id": "12345",
    ...     "person": {"full_name": "John Doe", "date_of_birth_iso": "2015-03-15"},
    ...     "school": {"name": "Lincoln School"},
    ...     "contact": {"postal_code": "M5V 3A8"}
    ... }
    >>> ctx = build_client_context(client, "en")
    >>> ctx["client_id"]
    '12345'
    >>> ctx["first_name"]
    'John'
    """
    # Extract person data (handle nested structure)
    person = client_data.get("person", {})
    contact = client_data.get("contact", {})
    school = client_data.get("school", {})
    board = client_data.get("board", {})

    # Get DOB in ISO format
    dob_iso = person.get("date_of_birth_iso") or person.get("date_of_birth", "")
    dob_display = person.get("date_of_birth_display", "") or dob_iso

    # Extract name components
    full_name = person.get("full_name", "")
    name_parts = full_name.split() if full_name else ["", ""]
    first_name = name_parts[0] if len(name_parts) > 0 else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    # Build context dict for template rendering
    context = {
        "client_id": string_or_empty(client_data.get("client_id", "")),
        "first_name": string_or_empty(first_name),
        "last_name": string_or_empty(last_name),
        "name": string_or_empty(full_name),
        "date_of_birth": string_or_empty(dob_display),
        "date_of_birth_iso": string_or_empty(dob_iso),
        "date_of_birth_iso_compact": string_or_empty(
            dob_iso.replace("-", "") if dob_iso else ""
        ),
        "school": string_or_empty(school.get("name", "")),
        "board": string_or_empty(board.get("name", "")),
        "postal_code": string_or_empty(contact.get("postal_code", "")),
        "city": string_or_empty(contact.get("city", "")),
        "province": string_or_empty(contact.get("province", "")),
        "street_address": string_or_empty(contact.get("street", "")),
        "language_code": language,  # ISO code: 'en' or 'fr'
    }

    if date_notice_delivery:
        context["date_notice_delivery"] = string_or_empty(date_notice_delivery)

    return context
