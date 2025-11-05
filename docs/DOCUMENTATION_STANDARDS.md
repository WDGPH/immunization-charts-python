# Documentation Standards

This document defines standards for docstrings and documentation to ensure code accessibility and maintainability during rapid development.

## Docstring Standards

### Module-Level Docstrings (Required)

Every `.py` file must start with a module-level docstring that explains its purpose and real-world significance:

```python
"""Brief one-line description of module purpose.

Extended description explaining:
- What problem this module solves
- Real-world usage significance (how it affects the immunization notices)
- Key responsibilities/boundaries
- Important notes about state, side effects, or dependencies
"""
```

**Example (good):**
```python
"""PDF validation and page counting for immunization notices.

Validates compiled PDF files and generates a manifest of page counts.
Used during Step 6 of the pipeline to ensure all notices compiled correctly
and to detect corrupted or incomplete PDFs before encryption or batching.

Writes metadata to output/metadata/<language>_page_counts_<run_id>.json
"""
```

**Example (poor):**
```python
"""PDF utilities."""  # Too vague, no significance context
```

### Function-Level Docstrings (Required)

Use **NumPy/SciPy docstring format** for consistency:

```python
def function_name(param1: str, param2: int, param3: Optional[str] = None) -> Dict[str, Any]:
    """Brief one-line summary (imperative mood).

    Extended description explaining:
    - What the function does and why
    - Real-world significance (when/why is this called? what output does it affect?)
    - Key limitations or assumptions
    - Processing flow if complex

    Parameters
    ----------
    param1 : str
        Description of what param1 is and constraints (e.g., "ISO date string")
    param2 : int
        Description with valid range (e.g., "batch size > 0, typically 1-100")
    param3 : Optional[str], default None
        Description; explain when to use vs omit

    Returns
    -------
    Dict[str, Any]
        Description of returned structure, e.g., {
            "status": "success|failure",
            "count": int,
            "details": List[str]
        }

    Raises
    ------
    ValueError
        If param2 <= 0 (include when/why)
    FileNotFoundError
        If required config files missing

    Examples
    --------
    >>> result = function_name("2015-01-01", 10)
    >>> result["count"]
    42

    Notes
    -----
    - This function reads from disk: `output/artifacts/preprocessed_clients_*.json`
    - Side effect: writes to `output/metadata/page_counts_*.json`
    - Performance: O(n) where n = number of PDFs
    """
```

### Test Module Docstrings (Required)

```python
"""Tests for preprocess module - data normalization and artifact generation.

Tests cover:
- Schema validation (required columns, data types)
- Data cleaning (dates, addresses, vaccine history)
- Client sorting and sequencing
- Artifact structure consistency
- Error handling for invalid inputs

Key assertion patterns:
- Verify artifact JSON matches expected schema
- Check client ordering (school → last_name → first_name)
- Validate vaccine name mapping against disease_map.json
"""
```

### Test Function Docstrings (Required)

Be specific about the scenario being tested and why it matters to real users:

```python
def test_preprocess_sorts_clients_by_school_then_name():
    """Verify clients are sorted deterministically for reproducible output.

    Real-world significance:
    - Enables comparisons between pipeline runs
    - Ensures sequence numbers (00001, 00002...) are stable
    - Required for batching by school to work correctly
    """
    # Implementation...

def test_preprocess_handles_missing_board_name():
    """Verify pipeline doesn't crash when board name is missing from input.

    Real-world significance:
    - Some school districts don't have explicit board assignments
    - Should auto-generate ID and log warning
    - Affects mail merge recipient determination
    """
    # Implementation...
```

## Documentation Principles

### 1. Real-World Significance Over Implementation Details

Not: "Calculate age from date of birth"

But: "Determine if notice goes to parent vs student based on age of student"

### 2. Trace to Outputs

Every function's docstring should explain how its output affects the final immunization notices. If it doesn't affect them, question whether it should exist.

### 3. Side Effects Are Not Hidden

Document:
- File I/O operations and paths
- Configuration dependencies
- Logging side effects
- State mutations

### 4. Type Hints Required

All function signatures must include type hints for parameters and return values.

## Documentation Checklist for New Code

Before submitting code, verify:

- [ ] **Module docstring** explains purpose and real-world significance
- [ ] **All functions** have docstrings with Parameters/Returns/Raises sections
- [ ] **All test functions** explain why the scenario matters for real users
- [ ] **Type hints** on all function signatures
- [ ] **Real-world significance** is clear (how does this affect the immunization notices?)
- [ ] **Side effects documented** (file I/O, config reads, logging)

## See Also

For code analysis standards (dead code detection, duplication analysis), see `CODE_ANALYSIS_STANDARDS.md`.

For testing documentation standards, see `TESTING_STANDARDS.md`.
