# Plan: Validate Schools and Daycares Against PHIX Reference List

**Status:** ✅ Implemented  
**Date:** 2026-01-14  

---

## Problem Statement

Input data contains school/daycare names that may not match the official PHIX (Public Health Information Exchange) reference list. This causes:
- Data quality issues in reports
- Difficulty linking records to official facility IDs
- No validation that facilities exist in the PHU's jurisdiction

## Solution

Add a validation step in preprocessing that matches input school/daycare names against the PHIX reference list, using fuzzy matching with configurable behavior for unmatched facilities.

---

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `pipeline/validate_phix.py` | Validation module with loading, matching, and batch validation |
| `tests/unit/test_validate_phix.py` | 26 unit tests covering all functionality |

### Files Modified

| File | Changes |
|------|---------|
| `config/parameters.yaml` | Added `phix_validation` configuration section |
| `pipeline/orchestrator.py` | Integrated validation into Step 2 (Preprocessing) |

### Configuration Options

```yaml
phix_validation:
  enabled: true
  reference_file: PHIX Reference Lists v5.2 - 2025Jun30.xlsx
  match_threshold: 85      # Fuzzy match score (0-100)
  unmatched_behavior: warn # warn | error | skip
  match_strategy: fuzzy    # exact | fuzzy
```

**Behavior modes:**
- `warn` - Log warning, continue processing all records
- `error` - Fail pipeline if any facilities don't match
- `skip` - Filter out records with unmatched facilities

---

## How It Works

### Pipeline Flow

```
Step 2: Preprocessing
├── read_input()
├── map_columns()
├── filter_columns()
├── ensure_required_columns()
├── check_addresses_complete()
├── validate_facilities()        ← NEW: PHIX validation
│   ├── Load PHIX Excel reference
│   ├── Normalize facility names
│   ├── Try exact match (100% confidence)
│   ├── Try fuzzy match if exact fails
│   ├── Write unmatched to CSV
│   └── Enrich DataFrame with PHIX_ID
├── build_preprocess_result()
└── write_artifact()
```

### PHIX Reference Format

The Excel file has one column per PHU, with values in `"FACILITY NAME - ID"` format:

```
| Algoma PHU                              | Brant PHU                    |
|----------------------------------------|------------------------------|
| ANNA MCCREA PUBLIC SCHOOL - 019186     | BRANTFORD ELEMENTARY - 12345 |
| SUNSHINE DAYCARE - AL-0003561          | MAPLE CHILDCARE - 67890      |
```

### Output

**Console:**
```
Step 2: Preprocessing
...
🏫 PHIX validation complete: 1,247 records validated
⚠️  3 facilities not found in PHIX reference. See output/unmatched_facilities.csv
```

**Enriched data (per record):**
- `PHIX_ID` - Official facility identifier
- `PHIX_MATCH_CONFIDENCE` - Match score (0-100)
- `PHIX_MATCH_TYPE` - "exact", "fuzzy", or "none"

**Unmatched report (`output/unmatched_facilities.csv`):**
```csv
facility_name,match_type,confidence
Lincon Elementary School,none,0
New Daycare Centre,none,0
```

---

## Design Decisions

### 1. Excel vs JSON for reference data

**Decision:** Keep Excel as source (official PHIX format PHUs receive)

**Rationale:**
- PHU staff can update without technical knowledge
- No manual conversion step to forget
- Caching makes load time acceptable

**Trade-off:** Slightly slower initial load (~0.5s vs ~50ms)

### 2. Integration point

**Decision:** After `check_addresses_complete()`, before `build_preprocess_result()`

**Rationale:**
- Validates after basic data normalization
- Can filter records before building client objects
- Follows existing validation pattern (addresses)

### 3. Fuzzy matching algorithm

**Decision:** Use `rapidfuzz.fuzz.ratio` with 85% threshold

**Rationale:**
- Already a project dependency
- Handles typos ("Elementry" → "Elementary")
- Threshold 85% catches minor typos without false positives

---

## Testing

```bash
# Run PHIX validation tests only
uv run pytest tests/unit/test_validate_phix.py -v

# Run all unit tests
uv run pytest -m unit
```

**Test coverage:**
- Parsing PHIX entries ("NAME - ID" format)
- Exact and fuzzy matching
- All three `unmatched_behavior` modes
- Edge cases (empty data, missing columns)
- Caching behavior

---

## Future Enhancements

1. **JSON cache layer** - Auto-generate JSON cache for faster loads
2. **CLI command** - `viper convert-phix` to pre-generate JSON
3. **PHU filtering** - Only load facilities for configured PHU
4. **Alias support** - Allow manual alias mappings for known variations
