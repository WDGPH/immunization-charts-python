# Configuration Files Reference

This directory contains all configuration files for the immunization pipeline. Each file has a specific purpose and is used at different stages of the pipeline.

---

## Contents

- [Data Flow Through Configuration Files](#data-flow-through-configuration-files)
- [Required Configuration Files](#required-configuration-files)
  - [`parameters.yaml`](#parametersyaml)
    - [Feature flags overview](#feature-flags-overview)
    - [Pipeline Lifecycle](#pipeline-lifecycle)
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

- `qr.enabled`: Enable or disable QR code generation (true/false)
- `encryption.enabled`: Enable or disable PDF encryption (true/false)
- `bundling.bundle_size`: Enable bundling with at most N clients per bundle (0 disables bundling)
- `bundling.group_by`: Bundle grouping strategy (null for sequential, `school`, or `board`)

#### Pipeline Lifecycle

The pipeline has two lifecycle phases controlled under `pipeline.*`:

**Before Run (`pipeline.before_run`)**:
- `clear_output_directory`: When true, removes all output except logs before starting a new run. Preserves the logs directory for audit trail. Set to true for clean re-runs; false to prompt before deleting.

**After Run (`pipeline.after_run`)**:
- `remove_artifacts`: When true, removes the `output/artifacts` directory (QR codes, Typst files). Use this to reclaim disk space after successful compilation and validation.
- `remove_unencrypted_pdfs`: When true and either encryption OR batching is enabled, removes non-encrypted PDFs from `output/pdf_individual/` after encryption/batching completes. When both encryption and batching are disabled, individual non-encrypted PDFs are assumed to be the final output and are preserved regardless of this setting.

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

QR code generation and validation is configured in `config/parameters.yaml` under the `qr` section. Payloads support flexible templating using client metadata as placeholders.

### QR Generation Settings

**`qr.enabled`** (boolean):
- When `true`: QR codes are generated during the notice generation step
- When `false`: No QR codes are embedded in PDFs
- Default: `true`

**`qr.payload_template`** (string):
- Template for QR code URL payload using placeholder fields
- Refer to the [Template Field Reference](#template-field-reference) for all available fields
- QR codes are square images (typically 570×570 pixels) embedded in the notice

### QR Validation

QR validation is controlled by the `qr_matches_link` rule under `pdf_validation.rules`:

```yaml
pdf_validation:
  rules:
    qr_matches_link: error  # or "warn" or "disabled"
```

**What it validates:**
1. QR codes are successfully extracted from the compiled PDF (by identifying square images)
2. QR codes are successfully decoded using OpenCV
3. Decoded QR payload matches at least one PDF hyperlink URL (from `/Annots` objects)

**Behavior:**
- When enabled with severity `error`: Pipeline fails if QR validation fails on any PDF
- When enabled with severity `warn`: Warnings are logged but pipeline continues
- Measurements recorded in validation JSON: `qr_codes_found`, `qr_code_payload`, `link_urls_found`, `link_url`

**Note:** QR validation can be enabled independently of QR generation. You can validate existing QR codes without re-generating them, or generate QR codes without validating them.

### Example Configuration

```yaml
qr:
  enabled: true
  payload_template: https://test-vaccine-portal.com?qrfn={first_name}&qrln={last_name}&qrdob={date_of_birth_iso}&qrsa={street_address}&qrct={city}&qrpc={postal_code}&qrid={client_id}

pdf_validation:
  rules:
    qr_matches_link: error
```

**Tips:**
- Use `{date_of_birth_iso}` (YYYY-MM-DD) or `{date_of_birth_iso_compact}` (YYYYMMDD) for predictable date formats
- Use `{client_id}` for unique identification in tracking systems
- Use `{language_code}` (`en` or `fr`) if the target system needs language-specific handling
- All placeholders are validated at runtime; typos will raise clear error messages

After updating the configuration, rerun the pipeline and regenerated notices will reflect the new QR payload.

---

## PDF Validation Configuration

The PDF validation step runs after compilation to enforce basic quality rules and surface layout issues. Configuration lives under `pdf_validation` in `config/parameters.yaml`.

Supported severity levels per rule:
- `disabled`: skip the check
- `warn`: include in summary but do not halt pipeline
- `error`: fail the pipeline if any PDFs violate the rule

Current rules:
- `exactly_two_pages`: Ensure each notice has exactly 2 pages (notice + immunization record)
- `signature_overflow`: Detect if the signature block spills onto page 2 (uses invisible Typst marker)
- `envelope_window_1_125`: Ensure contact area does not exceed 1.125" inches (uses invisible measurement marker)
- `client_id_presence`: Ensure the expected client ID appears somewhere in the PDF text (markerless text search)
- `qr_matches_link`: Ensure embedded QR codes are valid and decoded payload matches a PDF hyperlink URL

Example configuration:

```yaml
pdf_validation:
  rules:
    exactly_two_pages: warn
    signature_overflow: warn
    envelope_window_1_125: warn
    client_id_presence: error
    qr_matches_link: error
```

Behavior:
- The validation summary is always printed to the console.
- A JSON report is written to `output/metadata/<lang>_validation_<run_id>.json` with per-PDF results and aggregates.
- If any rule is set to `error` and fails, the pipeline stops with a clear error message listing failing rules and counts.
- The validation logic is implemented in `pipeline/validate_pdfs.py` and invoked by the orchestrator.
- Rules using invisible markers (signature_overflow, envelope_window_1_125) are embedded by the Typst templates without affecting appearance.
- Rules using markerless text search (client_id_presence) scan extracted PDF text; no template changes needed.
- QR validation (qr_matches_link) extracts and decodes QR images using OpenCV, then validates against PDF hyperlinks.

### Rule Details

**exactly_two_pages**
- Checks: `page_count == 2`
- Typical: Use `warn` or `error` (most notices should have exactly 2 pages)

**signature_overflow**
- Checks: Signature block ends on page 1 (uses `MARK_END_SIGNATURE_BLOCK` invisible marker)
- Typical: Use `warn` or `error`

**envelope_window_1_125**
- Checks: Contact table height ≤ 1.125 inches (uses `MEASURE_CONTACT_HEIGHT` invisible marker)
- Typical: Use `warn` or `error` (critical for Canada Post envelope windows)

**client_id_presence**
- Checks: Expected client ID found in extracted PDF text (markerless regex search for 10 digits)
- Source of truth: `preprocessed_clients_<run_id>.json` artifact
- Typical: Use `error` to catch notice generation bugs early

**qr_matches_link**
- Checks: Embedded QR code is valid and decoded payload matches at least one PDF hyperlink URL
- Source: QR extracted from square image (570×570px typical), hyperlinks from `/Annots` objects
- Typical: Use `error` if QR codes are required in notices
- Note: Requires `qr.enabled: true` to populate the QR codes; validation can still be enabled independently

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