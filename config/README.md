# Configuration Files Reference

This directory contains all configuration files for the immunization pipeline. Each file has a specific purpose and is used at different stages of the pipeline.

---

## Contents

- [Data Flow Through Configuration Files](#data-flow-through-configuration-files)
- [Required Configuration Files](#required-configuration-files)
  - [`parameters.yaml`](#parametersyaml)
    - [Feature flags overview](#feature-flags-overview)
    - [Date controls](#date-controls)
    - [Chart diseases header](#chart_diseases_header-configuration)
  - [`vaccine_reference.json`](#vaccine_referencejson)
  - [`disease_normalization.json`](#disease_normalizationjson)
  - [`translations/` Directory](#translations-directory)
- [QR Code Configuration](#qr-code-configuration)
- [PDF Validation Configuration](#pdf-validation-configuration)
- [PDF Encryption Configuration](#pdf-encryption-configuration)
- [🏷️ Template Field Reference](#template-field-reference)
- [Adding New Configurations](#adding-new-configurations)

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
  ↓
[validate_pdfs.py]
  └─ Validate PDFs (page counts, layout markers) and emit validation JSON
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

#### Feature flags overview

These are the most commonly adjusted options in `parameters.yaml`:

- `pipeline.auto_remove_output`: Automatically remove existing output before processing (true/false)
- `pipeline.keep_intermediate_files`: Preserve intermediate .typ, .json, and per-client .pdf files (true/false)
- `qr.enabled`: Enable or disable QR code generation (true/false)
- `encryption.enabled`: Enable or disable PDF encryption (true/false)
- `bundling.bundle_size`: Enable bundling with at most N clients per bundle (0 disables bundling)
- `bundling.group_by`: Bundle grouping strategy (null for sequential, `school`, or `board`)
- `cleanup.delete_unencrypted_pdfs`: Delete unencrypted PDFs after encryption/bundling (true/false; default: false)

#### Date controls
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

---

## 🏷️ Template Field Reference

Both QR code payloads and PDF password generation use **centralized template field validation** through the `TemplateField` enum (see `pipeline/enums.py`). This ensures consistent, safe placeholder handling across all template rendering steps.

### Available Template Fields

| Field | Format | Example | Notes |
|-------|--------|---------|-------|
| `client_id` | String | `12345` | Unique client identifier |
| `first_name` | String | `John` | Client's given name |
| `last_name` | String | `Doe` | Client's family name |
| `name` | String | `John Doe` | Full name (auto-combined) |
| `date_of_birth` | Localized date | `Jan 1, 2020` or `1 janvier 2020` | Formatted per language |
| `date_of_birth_iso` | ISO 8601 | `2020-01-01` | YYYY-MM-DD format |
| `date_of_birth_iso_compact` | Compact ISO | `20200101` | YYYYMMDD format (no hyphens) |
| `school` | String | `Lincoln School` | School name |
| `board` | String | `TDSB` | School board name |
| `street_address` | String | `123 Main St` | Full street address |
| `city` | String | `Toronto` | City/municipality |
| `province` | String | `ON` | Province/territory |
| `postal_code` | String | `M5V 3A8` | Postal/ZIP code |
| `language_code` | String | `en` or `fr` | ISO 639-1 language code |

### Template Validation

All template placeholders are **validated at runtime**:
- ✅ Placeholders must exist in the generated context
- ✅ Placeholders must be in the allowed field list (no typos like `{client_ID}`)
- ✅ Invalid placeholders raise clear error messages with allowed fields listed

This prevents silent failures from configuration typos and ensures templates are correct before processing.

---

## QR Code Configuration

QR code generation can be enabled/disabled in `config/parameters.yaml` under the `qr` section. The payload supports flexible templating using client metadata as placeholders.

Refer to the [Template Field Reference](#template-field-reference) for the complete list of supported placeholders.

Example override in `config/parameters.yaml`:

```yaml
qr:
  enabled: true
  payload_template: https://www.test-immunization.ca/update?client_id={client_id}&dob={date_of_birth_iso}&lang={language_code}
```

Tip:
- Use `{date_of_birth_iso}` or `{date_of_birth_iso_compact}` for predictable date formats
- The delivery date available to templates is `date_notice_delivery`

After updating the configuration, rerun the pipeline and regenerated notices will reflect the new QR payload.

---

## PDF Validation Configuration

The PDF validation step runs after compilation to enforce basic quality rules and surface layout issues. Configuration lives under `pdf_validation` in `config/parameters.yaml`.

Supported severity levels per rule:
- `disabled`: skip the check
- `warn`: include in summary but do not halt pipeline
- `error`: fail the pipeline if any PDFs violate the rule

Current rules:
- `envelope_window_1_125`: Ensure contact area does not exceed 1.125" inches
- `exactly_two_pages`: Ensure each notice has exactly 2 pages (notice + immunization record)
- `signature_overflow`: Detect if the signature block spills onto page 2 (uses invisible Typst marker)

Example configuration:

```yaml
pdf_validation:
  rules:
    envelope_window_1_125: error
    exactly_two_pages: warn
    signature_overflow: disabled
```

Behavior:
- The validation summary is always printed to the console.
- A JSON report is written to `output/metadata/<lang>_validation_<run_id>.json` with per-PDF results and aggregates.
- If any rule is set to `error` and fails, the pipeline stops with a clear error message listing failing rules and counts.
- The validation logic is implemented in `pipeline/validate_pdfs.py` and invoked by the orchestrator.
- The validation uses invisible markers embedded by the Typst templates to detect signature placement without affecting appearance.

---

## PDF Encryption Configuration

PDF encryption can be customized in `config/parameters.yaml` under the `encryption` section. Passwords are built via the same placeholder templating used for QR payloads.

Refer to the [Template Field Reference](#template-field-reference) for the complete list of supported placeholders.

Common strategies:
- Simple: `{date_of_birth_iso_compact}` – DOB only
- Compound: `{client_id}{date_of_birth_iso_compact}` – ID + DOB
- Formatted: `{client_id}-{date_of_birth_iso}` – hyphenated

Sample configurations in `config/parameters.yaml`:

```yaml
encryption:
  enabled: false
  password:
    template: "{date_of_birth_iso_compact}"

  # Or combine fields
  password:
    template: "{client_id}{date_of_birth_iso_compact}"

  # Or hyphenate
  password:
    template: "{client_id}-{date_of_birth_iso}"
```

All templates are validated at runtime to catch configuration errors early and provide clear, allowed-field guidance.

---

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