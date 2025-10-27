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
    └─ Emit artifact with canonical disease names
    ↓
Artifact JSON (canonical English disease names)
    ↓
[generate_notices.py]
    ├─ translations/{lang}_diseases_overdue.json → translate vaccines_due list
    ├─ translations/{lang}_diseases_chart.json → translate chart diseases
    └─ Inject into Typst template
    ↓
Typst Files (with localized disease names)
    ↓
[compile_notices.py]
    └─ Generate PDFs
```
---

## Required Configuration Files

---

### `parameters.yaml`
**Purpose**: Pipeline behavior configuration (feature flags, settings)

**Status**: Keep (not related to disease/vaccine reference)

**Usage**:
- QR code generation settings
- PDF encryption settings
- Batching configuration
- Chart disease selection

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