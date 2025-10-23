import subprocess
import pytest
from pathlib import Path
import os
import shutil
import re

TEST_LANG = "english"
PROJECT_DIR = Path(__file__).resolve().parents[1]
# Directory where generate_notices.sh will look for inputs and create outputs
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"


# Returns list of names of school batches in test
@pytest.fixture
def test_school_batch_names():
    return [
        "WHISKER_ELEMENTARY_01",
    ]


# Moves test inputs to main input directory
@pytest.fixture
def test_move_inputs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    keep_files = []

    input_path = PROJECT_DIR / "tests/test_data/input_generate_notices"
    for filename in os.listdir(input_path):
        if not os.path.exists(OUTPUT_DIR / filename):
            print(
                f"File {filename} not found at destination. Copying from test directory..."
            )
            shutil.copy(input_path / filename, OUTPUT_DIR / filename)
        else:
            print(f"File {filename} already exists at destination.")

            # Check whether to overwrite existing file in dir
            user_response = input("Do you want to overwrite the existing file? (y/n): ")
            if user_response.lower() == "y":
                print(f"Overwriting {filename}...")
                shutil.copy(input_path / filename, OUTPUT_DIR / filename)
            elif user_response.lower() == "n":
                print(
                    "Keeping existing file. Please note this may cause issues with testing."
                )
                keep_files.append(OUTPUT_DIR / filename)
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    # Return list of files not to be deleted at end of test
    return keep_files


# Cleans output folder before and after test
@pytest.fixture(autouse=True)
def clean_output_files(test_move_inputs):
    # Delete copied over test files after test
    yield
    input_path = PROJECT_DIR / "tests/test_data/input_generate_notices"
    for filename in os.listdir(input_path):
        if not os.path.exists(OUTPUT_DIR / filename):
            print(f"File {filename} not found in output folder.")
        else:
            if OUTPUT_DIR / filename not in test_move_inputs:
                print(f"Cleaning file {filename} from output folder.")
                (OUTPUT_DIR / filename).unlink()
            else:
                print(f"Not removing file {filename} from output folder.")


# Run tests for Generate Notices step of pipeline
def test_generate_notices(test_school_batch_names, test_move_inputs):
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

        # Remove test output file
        filepath.unlink()
