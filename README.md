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

## 🛠️ Pipeline Overview

## 🚦 Pipeline Steps (`run_pipeline.sh`)

The main pipeline script automates the end-to-end workflow for generating immunization notices and charts. Below are the key steps:

1. **Preprocessing**  
   Runs `preprocess.py` to clean, validate, and structure input data.

2. **Record Count**  
   Counts the number of records in the input CSV (excluding the header).

3. **Generating Notices**  
   Calls `generate_notices.sh` to create Typst templates for each client.

4. **Compiling Notices**  
   Ensures the `conf.typ` template is present, then runs `compile_notices.sh` to generate PDF notices.

5. **PDF Length Check**  
   Uses `count_pdfs.py` to check the length of each compiled PDF notice for quality control.

6. **Cleanup**  
   Runs `cleanup.sh` to remove temporary files and tidy up the output directory.

7. **Summary**  
   Prints a summary of timings for each step, batch size, and total record count.

**Usage Example:**
```bash
cd scripts
./run_pipeline.sh <input_file> <language> [--no-cleanup]
```
- `<input_file>`: Name of the input file (e.g., `students.xlsx`)
- `<language>`: Language code (`en` or `fr`)
- `--no-cleanup` (optional): Skip deleting intermediate Typst artifacts.

> ℹ️ **Typst preview note:** The WDGPH code-server development environments render Typst files via Tinymist. The shared template at `scripts/conf.typ` only defines helper functions, colour tokens, and table layouts that the generated notice `.typ` files import; it doesn't emit any pages on its own, so Tinymist has nothing to preview if attempted on this file. To examine the actual markup that uses these helpers, run the pipeline with `--no-cleanup` so the generated notice `.typ` files stay in `output/json_<lang>/` for manual inspection.

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

The Python-based pipeline `preprocess.py` orchestrates immunization record preparation and structuring. It replaces the previous Bash script and provides:

- Reading and validating input files (CSV/Excel)
- Separating data by school
- Splitting files into batch chunks
- Cleaning and transforming client data
- Building structured notices (JSON + client ID list)

Logging is written to `preprocess.log` for traceability.

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


## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for details of each release.