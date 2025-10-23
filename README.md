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
- **Resilience**: Each step can be re-run independently if needed
- **Simplicity**: No complex data structures passed between components

### Data Management

The pipeline produces a single **normalized JSON artifact** (`preprocessed_clients_<run_id>.json`) during preprocessing. This artifact serves as the canonical source of truth:

- **Created by:** `preprocess.py` (Step 2) - contains sorted clients with enriched metadata
- **Consumed by:** `generate_notices.py` (Step 3) and `batch_pdfs.py` (Step 7)
- **Format:** Single JSON file with run metadata, total client count, warnings, and per-client details

Client data flows through specialized handlers during generation:

| Stage | Input | Processing | Output |
|-------|-------|-----------|--------|
| **QR Generation** | In-memory `ClientRecord` objects | `build_template_context()` → `generate_qr_code()` | PNG images in `artifacts/qr_codes/` |
| **Typst Template** | In-memory `ClientRecord` objects | `render_notice()` → template rendering | `.typ` files in `artifacts/typst/` |
| **PDF Compilation** | Filesystem glob of `.typ` files | Typst subprocess | PDF files in `pdf_individual/` |
| **PDF Batching** | In-memory `ClientArtifact` objects | Grouping and manifest generation | Batch PDFs in `pdf_combined/` |

Each step reads the JSON fresh when needed—there is no shared in-memory state passed between steps through the orchestrator.

### Client Ordering

Clients are deterministically ordered during preprocessing by: **school name → last name → first name → client ID**, ensuring consistent, reproducible output across pipeline runs. Each client receives a deterministic sequence number (`00001`, `00002`, etc.) that persists through all downstream operations.

## 🚦 Pipeline Steps

The main pipeline orchestrator (`run_pipeline.py`) automates the end-to-end workflow for generating immunization notices and charts. Below are the key steps:

1. **Output Preparation**  
   Prepares the output directory, optionally removing existing contents while preserving logs.

2. **Preprocessing**  
   Runs `preprocess.py` to clean, validate, and structure input data into a normalized JSON artifact.

3. **Generating Notices**  
   Calls `generate_notices.py` to create Typst templates for each client from the preprocessed artifact.

4. **Compiling Notices**  
   Runs `compile_notices.py` to compile Typst templates into individual PDF notices.

5. **PDF Validation**  
   Uses `count_pdfs.py` to validate the page count of each compiled PDF for quality control.

6. **Batching PDFs** (optional)  
   When enabled, combines individual PDFs into batches using `batch_pdfs.py` with optional grouping by school or board.

7. **Cleanup**  
   Removes intermediate files (.typ, .json) to tidy up the output directory.

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
- `pipeline.auto_remove_output`: Automatically remove existing output (true/false)
- `pipeline.keep_intermediate_files`: Preserve .typ, .json, and per-client .pdf files (true/false)
- `batching.batch_size`: Enable batching with at most N clients per batch (0 disables)
- `batching.group_by`: Batch grouping strategy (null, "school", or "board")

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

We're expanding automated checks to ensure feature additions do not impact existing functionality, and to improve the overall quality of the project. After syncing the virtual environment once with `uv sync`, you can run the current test suite using:

```bash
uv run pytest
```

You'll see a quick summary of which checks ran (right now that’s the clean-up helpers, with more on the way). A final line ending in `passed` means the suite finished successfully.

> ✅ Before running the command above, make sure you've installed the `dev` group at least once (`uv sync --group dev`) so that the testing dependencies are available.

## 📂 Input Data

- Use data extracts from [Panorama PEAR](https://accessonehealth.ca/)
- Place input files in the `input/` subfolder (not tracked by Git)
- Files must be `.xlsx` format with a **single worksheet** per file

## Preprocessing

The `preprocess.py` module orchestrates immunization record preparation and structuring. It provides:

- Reading and validating input files (CSV/Excel) with schema enforcement
- Cleaning and transforming client data (dates, addresses, vaccine history)
- Synthesizing stable school/board identifiers when they are missing in the extract
- Assigning deterministic per-client sequence numbers sorted by school → last name → first name
- Emitting a normalized run artifact at `output/artifacts/preprocessed_clients_<run_id>.json`

Logging is written to `output/logs/preprocess_<run_id>.log` for traceability.

### Main Class: `ClientDataProcessor`

Handles per-client transformation of vaccination and demographic data into structured notices.

#### Initialization

```python
ClientDataProcessor(
    df, disease_map, vaccine_ref, ignore_agents, delivery_date, language="en"
)
```

- `df (pd.DataFrame)`: Raw client data
- `disease_map (dict)`: Maps disease descriptions to vaccine names
- `vaccine_ref (dict)`: Maps vaccines to diseases
- `ignore_agents (list)`: Agents to skip
- `delivery_date (str)`: Processing run date (e.g., "2024-06-01")
- `language (str)`: "en" or "fr"

#### Key Methods

- `process_vaccines_due(vaccines_due: str) -> str`: Maps overdue diseases to vaccine names
- `process_received_agents(received_agents: str) -> list`: Extracts and normalizes vaccination history
- `build_notices()`: Populates the notices dictionary with structured client data
- `save_output(outdir: Path, filename: str)`: Writes results to disk

### Utility Functions

- `detect_file_type(file_path: Path) -> str`: Returns file extension
- `read_input(file_path: Path) -> pd.DataFrame`: Reads CSV/Excel into DataFrame
- `separate_by_column(data: pd.DataFrame, col_name: str, out_path: Path)`: Splits DataFrame by column value
- `split_batches(input_dir: Path, output_dir: Path, batch_size: int)`: Splits CSV files into batches
- `check_file_existence(file_path: Path) -> bool`: Checks if file exists
- `load_data(input_file: str) -> pd.DataFrame`: Loads and normalizes data
- `validate_transform_columns(df: pd.DataFrame, required_columns: list)`: Validates required columns
- `separate_by_school(df: pd.DataFrame, output_dir: str, school_column: str = "School Name")`: Splits dataset by school

### Script Entry Point

Command-line usage:

```bash
python preprocess.py <input_dir> <input_file> <output_dir> [language]
```

- `language` (optional): Use `en` or `fr`. Defaults to `en` when omitted.

Steps performed:

1. Load data
2. Validate schema
3. Separate by school
4. Split into batches
5. For each batch:
    - Clean address fields
    - Build notices with `ClientDataProcessor`
    - Save JSON + client IDs

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
