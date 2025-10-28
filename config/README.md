# Configuration Files Reference

This directory contains all configuration files for the immunization pipeline. Each file has a specific purpose and is used at different stages of the pipeline.

---

## Data Flow Through Configuration Files

```
Raw Input (from CSV/Excel)
    ↓
[preprocess.py]
    ├─ disease_normalization.json → normalize variants
    ├─ vaccine_reference.json → expand vaccines to diseases
    ├─ parameters.yaml.chart_diseases_header → filter diseases not in chart → "Other"
    └─ Emit artifact with filtered disease names
    ↓
Artifact JSON (canonical English disease names, filtered by chart config)
    ↓
[generate_notices.py]
    ├─ parameters.yaml.chart_diseases_header → load chart disease list
    ├─ translations/{lang}_diseases_chart.json → translate each disease name
    ├─ translations/{lang}_diseases_overdue.json → translate vaccines_due list
    └─ Inject translated diseases into Typst template
    ↓
Typst Files (with localized, filtered disease names)
    ↓
[compile_notices.py]
    └─ Generate PDFs
```
---

## Required Configuration Files

---

### `parameters.yaml`
**Purpose**: Pipeline behavior configuration (feature flags, settings, and chart disease filtering)

**Usage**:
- QR code generation settings
- PDF encryption settings
- Batching configuration
- **Date controls for data freshness and eligibility logic**
- **Chart disease selection via `chart_diseases_header` (CRITICAL)**

**Date controls:**
- `date_data_cutoff` (ISO 8601 string) records when the source data was extracted. It renders in notices using the client's language via Babel so that readers see a localized calendar date. Change this only when regenerating notices from a fresher extract.
- `date_notice_delivery` (ISO 8601 string) fixes the reference point for age-based eligibility checks and QR payloads. Preprocessing uses this value to decide if a client is 16 or older, so adjust it cautiously and keep it aligned with the actual delivery or mailing date.

**`chart_diseases_header` Configuration:**

This list defines which diseases appear as columns in the immunization chart:

```yaml
chart_diseases_header:
  - Diphtheria
  - Tetanus
  - Pertussis
  - Polio
  - Hib
  - Pneumococcal
  - Rotavirus
  - Measles
  - Mumps
  - Rubella
  - Meningococcal
  - Varicella
  - Other
```

**Disease Filtering and "Other" Category:**

1. **During Preprocessing (`preprocess.py`):**
   - Diseases from vaccine records are checked against `chart_diseases_header`
   - Diseases **not** in the list are **collapsed into "Other"**
   - This ensures only configured diseases appear as separate columns

2. **During Notice Generation (`generate_notices.py`):**
   - Each disease name in `chart_diseases_header` is **translated to the target language**
   - Translations come from `translations/{lang}_diseases_chart.json`
   - Translated list is passed to Typst template
   - The template renders column headers using **Python-translated names**, not raw config values

**Impact:**
- Chart columns only show diseases in this list
- Unplanned/unexpected diseases are grouped under "Other"
- All column headers are properly localized before template rendering
- No runtime lookups needed in Typst; translations applied in Python

---

### `vaccine_reference.json`
**Purpose**: Maps vaccine codes to the diseases they protect against (canonical disease names)

**Format**: 
```json
{
  "VACCINE_CODE": ["Disease1", "Disease2", ...],
  ...
}
```

**Usage**:
- Loaded in `orchestrator.py` step 2 (preprocessing)
- Used in `preprocess.py`:
  - `enrich_grouped_records()` expands vaccine codes to disease names
  - Maps received vaccine records to canonical disease names
- All disease names MUST be canonical (English) forms

**Example**:
```json
{
  "DTaP": ["Diphtheria", "Tetanus", "Pertussis"],
  "IPV": ["Polio"],
  "MMR": ["Measles", "Mumps", "Rubella"]
}
```

**Canonical diseases** (must match these exactly):
- Diphtheria
- HPV
- Hepatitis B
- Hib
- Measles
- Meningococcal
- Mumps
- Pertussis
- Pneumococcal
- Polio
- Rotavirus
- Rubella
- Tetanus
- Varicella
- Other

---

### `disease_normalization.json`
**Purpose**: Normalizes raw input disease strings to canonical disease names

**Format**:
```json
{
  "raw_input_variant": "canonical_disease_name",
  ...
}
```

**Usage**:
- Loaded in `pipeline/translation_helpers.py`
- Called by `normalize_disease()` in preprocessing
- Handles input variants that differ from canonical names
- If a variant is not in this map, the input is returned unchanged (may still map via other mechanisms)

**Example**:
```json
{
  "Poliomyelitis": "Polio",
  "Human papilloma virus infection": "HPV",
  "Haemophilus influenzae infection, invasive": "Hib"
}
```

---

### `translations/` Directory
**Purpose**: Stores language-specific translations of disease names for display

**Structure**:
```
translations/
├── en_diseases_overdue.json    # English labels for overdue vaccines list
├── fr_diseases_overdue.json    # French labels for overdue vaccines list
├── en_diseases_chart.json      # English labels for immunization chart
└── fr_diseases_chart.json      # French labels for immunization chart
```

**Format** (same for all translation files):
```json
{
  "canonical_disease_name": "display_label",
  ...
}
```

**Usage**:
- Loaded in `pipeline/translation_helpers.py`
- Called by `display_label()` when rendering notices
- Two domains:
  - **diseases_overdue**: Labels for the "vaccines due" section
  - **diseases_chart**: Labels for the immunization history table
- Different labels possible per domain (e.g., "Polio" vs "Poliomyelitis" in chart)

**Example**:
```json
{
  "Polio": "Polio",
  "Measles": "Measles",
  "Diphtheria": "Diphtheria"
}
```


## Adding New Configurations

### Adding a New Disease

1. **Update `vaccine_reference.json`**:
   - Add vaccine code mapping if needed
   - Ensure all diseases use canonical names

2. **Update all translation files** (required):
   - `translations/en_diseases_overdue.json`
   - `translations/fr_diseases_overdue.json`
   - `translations/en_diseases_chart.json`
   - `translations/fr_diseases_chart.json`

3. **Update `disease_normalization.json`** (if needed):
   - Add any input variants that map to this disease

4. **Test**:
   ```bash
   uv run pytest tests/unit/test_translation_helpers.py::TestMultiLanguageSupport -v
   ```

### Adding a New Language

1. **Extend Language enum** in `pipeline/enums.py`

2. **Create translation files**:
   - `translations/{lang}_diseases_overdue.json`
   - `translations/{lang}_diseases_chart.json`

3. **Populate translations**:
   - Copy English content
   - Translate all disease names to target language

4. **Test**:
   ```bash
   uv run pytest -m "not e2e"
   ```