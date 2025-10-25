# 🩺 Immunization Charts (python Version)

**Current version:** v0.1.0  

## 📘 Introduction

This project provides a Python and Bash-based workflow for generating **personalized immunization history charts** and **notice letters** for children overdue for mandated vaccinations under the **Child Care and Early Years Act (CCEYA)** and ISPA.

Reports are generated in PDF format using [Typst](https://typst.app) and a custom report template.

## ⚙️ Environment Setup

- Written in **Bash** and **Python**
- Uses [Typst](https://typst.app) for typesetting
- Python dependencies managed via `pyproject.toml` and [uv](https://github.com/astral-sh/uv)

### Virtual Environment

Install all dependencies (and create the `.venv` if it doesn't yet exist) before doing anything else:

```bash
uv sync
source .venv/bin/activate
```

> ℹ️ `uv sync` only installs the core runtime packages by default. If you're planning to run tests or other dev tools, include the development group once via `uv sync --group dev` (or `uv sync --all-groups` if you prefer everything).

### Code Quality & Pre-commit Hooks

To enable automatic code linting and formatting on every commit, initialize pre-commit hooks:

```bash
uv sync --group dev                 # Install development tools (pre-commit, pytest, etc.)
uv run pre-commit install           # Initialize git hooks
```

Now, whenever you commit changes, the pre-commit hook automatically:
- **Lints** your code with `ruff check --fix` (auto-fixes issues when possible)
- **Formats** your code with `ruff format` (enforces consistent style)

If any check fails, your commit is blocked until you fix the issues. You can also run checks manually anytime:

```bash
uv run pre-commit run --all-files   # Check all files
```

## 🛠️ Pipeline Overview & Architecture

This section describes how the pipeline orchestrates data flow and manages state across processing steps.

### Orchestration Model

The pipeline follows a **sequential, stateless step architecture** where each processing step:

1. **Reads fresh input** from disk (either Excel files or the preprocessed JSON artifact)
2. **Processes data** independently without holding state between steps
3. **Writes output** to disk for the next step to discover
4. **Never passes in-memory objects** between steps via the orchestrator

This design ensures:
- **Modularity**: Steps can be understood, tested, and modified in isolation
- **Resilience**: Each step can be re-run independently if needed (e.g., if Step 4 fails, fix the code and re-run Steps 4-9 without reprocessing)
- **Simplicity**: No complex data structures passed between components
- **Reproducibility**: Same input always produces same output across runs

### Data Management

The pipeline produces a single **normalized JSON artifact** (`preprocessed_clients_<run_id>.json`) during preprocessing. This artifact serves as the canonical source of truth:

- **Created by:** `preprocess.py` (Step 2) - contains sorted clients with normalized metadata
- **Consumed by:** `generate_qr_codes.py` (Step 3), `generate_notices.py` (Step 4), and `batch_pdfs.py` (Step 8)
- **Format:** Single JSON file with run metadata, total client count, warnings, and per-client details

Client data flows through specialized handlers during generation:

| Stage | Input | Processing | Output |
|-------|-------|-----------|--------|
| **Preprocessing** | Excel file | Data normalization, sorting, age calculation | `preprocessed_clients_<run_id>.json` |
| **QR Generation** | Preprocessed JSON | Payload formatting → PNG generation | PNG images in `artifacts/qr_codes/` |
| **Typst Template** | Preprocessed JSON | Template rendering with QR reference | `.typ` files in `artifacts/typst/` |
| **PDF Compilation** | Filesystem glob of `.typ` files | Typst subprocess | PDF files in `pdf_individual/` |
| **PDF Batching** | In-memory `ClientArtifact` objects | Grouping and manifest generation | Batch PDFs in `pdf_combined/` |

Each step reads the JSON fresh when needed—there is no shared in-memory state passed between steps through the orchestrator.

### Client Ordering

Clients are deterministically ordered during preprocessing by: **school name → last name → first name → client ID**, ensuring consistent, reproducible output across pipeline runs. Each client receives a deterministic sequence number (`00001`, `00002`, etc.) that persists through all downstream operations.

## 🚦 Pipeline Steps

The main pipeline orchestrator (`run_pipeline.py`) automates the end-to-end workflow for generating immunization notices and charts. Below are the nine sequential steps:

1. **Output Preparation** (`prepare_output.py`)  
   Prepares the output directory, optionally removing existing contents while preserving logs.

2. **Preprocessing** (`preprocess.py`)  
   Cleans, validates, and structures input data into a normalized JSON artifact (`preprocessed_clients_<run_id>.json`).

3. **Generating QR Codes** (`generate_qr_codes.py`, optional)  
   Generates QR code PNG files from templated payloads. Skipped if `qr.enabled: false` in `parameters.yaml`.

4. **Generating Notices** (`generate_notices.py`)  
   Renders Typst templates (`.typ` files) for each client from the preprocessed artifact, with QR code references.

5. **Compiling Notices** (`compile_notices.py`)  
   Compiles Typst templates into individual PDF notices using the `typst` command-line tool.

6. **Validating PDFs** (`count_pdfs.py`)  
   Validates the page count of each compiled PDF and generates a page count manifest for quality control.

7. **Encrypting PDFs** (`encrypt_notice.py`, optional)  
   When `encryption.enabled: true`, encrypts individual PDFs using client metadata as password.

8. **Batching PDFs** (`batch_pdfs.py`, optional)  
   When `batching.batch_size > 0`, combines individual PDFs into batches with optional grouping by school or board. Skipped if encryption is enabled.

9. **Cleanup** (`cleanup.py`)  
   Removes intermediate files (.typ, .json, per-client PDFs) if `pipeline.keep_intermediate_files: false`.

**Usage Example:**
```bash
uv run viper <input_file> <language> [--output-dir PATH]
```

**Required Arguments:**
- `<input_file>`: Name of the input file (e.g., `students.xlsx`)
- `<language>`: Language code (`en` or `fr`)

**Optional Arguments:**
- `--input-dir PATH`: Input directory (default: ../input)
- `--output-dir PATH`: Output directory (default: ../output)
- `--config-dir PATH`: Configuration directory (default: ../config)

**Configuration:**
All pipeline behavior is controlled via `config/parameters.yaml`:
- `pipeline.auto_remove_output`: Automatically remove existing output before processing (true/false)
- `pipeline.keep_intermediate_files`: Preserve intermediate .typ, .json, and per-client .pdf files (true/false)
- `qr.enabled`: Enable or disable QR code generation (true/false)
- `encryption.enabled`: Enable or disable PDF encryption (true/false, disables batching if true)
- `batching.batch_size`: Enable batching with at most N clients per batch (0 disables batching)
- `batching.group_by`: Batch grouping strategy (null for sequential, "school", or "board")

**Examples:**
```bash
# Basic usage
uv run viper students.xlsx en

# Override output directory
uv run viper students.xlsx en --output-dir /tmp/output
```

> ℹ️ **Typst preview note:** The WDGPH code-server development environments render Typst files via Tinymist. The shared template at `scripts/conf.typ` only defines helper functions, colour tokens, and table layouts that the generated notice `.typ` files import; it doesn't emit any pages on its own, so Tinymist has nothing to preview if attempted on this file. To examine the actual markup that uses these helpers, run the pipeline with `pipeline.keep_intermediate_files: true` in `config/parameters.yaml` so the generated notice `.typ` files stay in `output/artifacts/` for manual inspection.

**Outputs:**
- Processed notices and charts in the `output/` directory
- Log and summary information in the terminal

## 🧪 Running Tests

The test suite is organized in three layers (see `docs/TESTING_STANDARDS.md` for details):

**Quick checks (unit tests, <100ms each):**
```bash
uv run pytest -m unit
```

**Integration tests (step interactions, 100ms–1s each):**
```bash
uv run pytest -m integration
```

**End-to-end tests (full pipeline, 1s–30s each):**
```bash
uv run pytest -m e2e
```

**All tests:**
```bash
uv run pytest
```

**With coverage report:**
```bash
uv run pytest --cov=scripts --cov-report=html
```

View coverage in `htmlcov/index.html`.

**For CI/local development (skip slow E2E tests):**
```bash
uv run pytest -m "not e2e"
```

> ✅ Before running tests, make sure you've installed the `dev` group at least once (`uv sync --group dev`) so that testing dependencies are available.

## 📂 Input Data

- Use data extracts from [Panorama PEAR](https://accessonehealth.ca/)
- Place input files in the `input/` subfolder (not tracked by Git)
- Files must be `.xlsx` format with a **single worksheet** per file

## Preprocessing

The `preprocess.py` (Step 2) module reads raw input data and produces a normalized JSON artifact.

### Processing Workflow

- **Input:** Excel file with raw client vaccination records
- **Processing:**
  - Validates schema (required columns, data types)
  - Cleans and transforms client data (dates, addresses, vaccine history)
  - Determines over/under 16 years old for recipient determination (uses `delivery_date` from `parameters.yaml`)
  - Assigns deterministic per-client sequence numbers sorted by: school → last name → first name → client ID
  - Maps vaccine history against disease reference data
  - Synthesizes stable school/board identifiers when missing
- **Output:** Single JSON artifact at `output/artifacts/preprocessed_clients_<run_id>.json`

Logging is written to `output/logs/preprocess_<run_id>.log` for traceability.

### Artifact Structure

The preprocessed artifact contains:

```json
{
  "run_id": "20251023T200355",
  "language": "en",
  "total_clients": 5,
  "warnings": [],
  "clients": [
    {
      "sequence": 1,
      "client_id": "1009876545",
      "person": {"first_name": "...", "last_name": "...", "date_of_birth": "..."},
      "school": {"name": "...", "board": "..."},
      "contact": {"street_address": "...", "city": "...", "postal_code": "...", "province": "..."},
      "vaccines": {"due": "...", "received": [...]},
      "metadata": {"recipient": "...", "over_16": false}
    },
    ...
  ]
}
```

## QR Code Configuration

The QR payload can be customised in `config/parameters.yaml` under the `qr` section. Each string behaves like a Python f-string and can reference the placeholders listed below. The preprocessing step validates the configuration on every run and raises an error if it encounters an unknown placeholder or invalid format, helping surface issues before templates are rendered.

**Available placeholders**
- `client_id`
- `first_name`
- `last_name`
- `name`
- `date_of_birth` (language-formatted string)
- `date_of_birth_iso` (`YYYY-MM-DD`)
- `school`
- `city`
- `postal_code`
- `province`
- `street_address`
- `language` (`english` or `french`)
- `language_code` (`en` or `fr`)
- `delivery_date`

**Sample override in `config/parameters.yaml`**
```yaml
qr:
  payload_template:
    english: "https://portal.example.ca/update?client_id={client_id}&dob={date_of_birth_iso}"
    french: "https://portal.example.ca/update?client_id={client_id}&dob={date_of_birth_iso}"
```

## PDF Encryption Configuration

PDF encryption can be customised in `config/parameters.yaml` under the `encryption` section. The password generation supports flexible templating similar to QR payloads, allowing you to combine multiple fields with custom formats.

**Available placeholders for password templates**
- `client_id`
- `first_name`
- `last_name`
- `name`
- `date_of_birth` (language-formatted string)
- `date_of_birth_iso` (`YYYY-MM-DD`)
- `date_of_birth_iso_compact` (`YYYYMMDD` - compact format)
- `school`
- `city`
- `postal_code`
- `province`
- `street_address`
- `language` (`english` or `french`)
- `language_code` (`en` or `fr`)
- `delivery_date`

**Sample configurations in `config/parameters.yaml`**
```yaml
encryption:
  # Use only DOB in compact format (default)
  password:
    template: "{date_of_birth_iso_compact}"

  # Combine client_id and DOB
  password:
    template: "{client_id}{date_of_birth_iso_compact}"

  # Use formatted DOB with dashes
  password:
    template: "{client_id}-{date_of_birth_iso}"
```

Update the configuration file, rerun the pipeline, and regenerated notices will reflect the new QR payload.
## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for details of each release.
