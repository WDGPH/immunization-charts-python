import subprocess
import pytest
from pathlib import Path
import os
import shutil
import re

TEST_LANG = "english"
PROJECT_DIR = Path(__file__).resolve().parents[1]
TEST_OUTPUT_DIR = PROJECT_DIR / "tests/test_data/input_generate_notices"
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"
TMP_TEST_DIR = PROJECT_DIR / "tests/tmp_test_dir/test_generate_notices_tmp"


# Returns list of names of school batches in test
@pytest.fixture
def test_school_batch_names():
    return [
        "WHISKER_ELEMENTARY_01",
    ]


# Cleans output folder before and after test
@pytest.fixture(autouse=True)
def clean_output_files():
    tmp_filenames = {}

    # Move existing output directories to temporary directory during testing
    if os.path.exists(PROJECT_DIR / "output"):
        print(f"Temporarily moving output folder to {TMP_TEST_DIR}/output")
        os.makedirs(TMP_TEST_DIR, exist_ok=True)
        shutil.move(PROJECT_DIR / "output", TMP_TEST_DIR / "output")
        tmp_filenames[PROJECT_DIR / "output"] = TMP_TEST_DIR / "output"

    # Remake output dir for test files
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_path = PROJECT_DIR / "tests/test_data/input_compile_notices"
    for filename in os.listdir(input_path):
        if not os.path.exists(OUTPUT_DIR / filename):
            print(
                f"File {filename} not found at destination. Copying from test directory..."
            )
            shutil.copy(input_path / filename, OUTPUT_DIR / filename)
        else:
            print(f"File {filename} already exists at destination.")

    yield

    # Restore original files and folders
    for tmp_filename in tmp_filenames.keys():
        # Remove generated folders
        if os.path.exists(tmp_filename):
            if os.path.isdir(tmp_filename):
                shutil.rmtree(tmp_filename)
            else:
                tmp_filename.unlink()

        print(f"Restoring original '{tmp_filename}'.")
        shutil.move(tmp_filenames[tmp_filename], tmp_filename)

    # Remove temporary dir for renamed files
    if os.path.exists(TMP_TEST_DIR):
        shutil.rmtree(TMP_TEST_DIR)


# Run tests for Generate Notices step of pipeline
def test_generate_notices(test_school_batch_names):
    # Test that supplementary files exist
    assert (PROJECT_DIR / "assets/logo.png").exists()
    assert (PROJECT_DIR / "assets/signature.png").exists()
    assert (PROJECT_DIR / "config/parameters.yaml").exists()

    # Set working directory to scripts
    working_dir = PROJECT_DIR / "scripts"

    # Run the script
    script_path = working_dir / "generate_notices.sh"

    result = subprocess.run(
        [script_path, TEST_LANG], cwd=working_dir, capture_output=True, text=True
    )

    assert result.returncode == 0, f"Script failed: {result.stderr}"

    # Check that .typ files were created for each school batch
    for test_school_batch_name in test_school_batch_names:
        filepath = OUTPUT_DIR / (test_school_batch_name + "_immunization_notice.typ")

        # Check that .typ file exists
        assert os.path.exists(filepath), (
            f"Missing .typ file: {test_school_batch_name}_immunization_notice.typ"
        )

        # Check that file is not empty
        assert os.path.getsize(filepath) != 0, (
            f"Empty .typ file: {test_school_batch_name}_immunization_notice.typ"
        )

        content = filepath.read_text()

        # Match a #let statement that uses csv()
        match = re.search(
            r'#let\s+(\w+)\s*=\s*csv\("([^"]+)",\s*delimiter:\s*"([^"]+)",\s*row-type:\s*(\w+)\)',
            content,
        )

        assert match, "No valid #let csv(...) statement found in .typ file"

        var_name, csv_file, delimiter, row_type = match.groups()

        # Validate values
        assert var_name == "client_ids", f"Unexpected variable name: {var_name}"
        assert csv_file.endswith(".csv"), f"CSV file reference is invalid: {csv_file}"
        assert csv_file == f"{test_school_batch_name}_client_ids.csv", (
            f"CSV file name in .typ file does not match school batch: {csv_file}"
        )
        assert delimiter == ",", f"Unexpected delimiter: {delimiter}"
        assert row_type == "array", f"Unexpected row-type: {row_type}"

        # Check that the referenced file exists
        csv_path = filepath.parent / csv_file
        assert csv_path.exists(), f"Referenced CSV file does not exist: {csv_path}"
        assert os.path.getsize(csv_path) != 0, f"Referenced CSV file empty: {csv_path}"

        # Match a #let statement that uses json()
        match = re.search(
            r'let\s+(\w+)\s*=\s*json\("([^"]+\.json)"\)\.at\(\w+\)', content
        )

        assert match, "No valid #let json(...) statement found in .typ file"

        var_name, json_file = match.groups()

        # Validate values
        assert var_name == "data", f"Unexpected variable name: {var_name}"
        assert json_file.endswith(".json"), (
            f"JSON file reference is invalid: {json_file}"
        )
        assert json_file == f"{test_school_batch_name}.json", (
            f"JSON file name in .typ file does not match school batch: {json_file}"
        )

        # Check that the referenced file exists
        json_path = filepath.parent / json_file
        assert json_path.exists(), f"Referenced JSON file does not exist: {json_path}"
        assert os.path.getsize(json_path) != 0, (
            f"Referenced JSON file empty: {json_path}"
        )

        # Remove test output file
        filepath.unlink()
