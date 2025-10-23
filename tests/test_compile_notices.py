import subprocess
import pytest
from pathlib import Path
import shutil
import os
from pypdf import PdfReader
import re
import pandas as pd

TEST_LANG = "english"
PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"


# Moves test inputs to main input directory
@pytest.fixture
def test_move_inputs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    keep_files = []

    input_path = PROJECT_DIR / "tests/test_data/input_compile_notices"
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


# Returns list of names of school batches in test
@pytest.fixture
def test_school_batch_names():
    return [
        "WHISKER_ELEMENTARY_01",
    ]


# Cleans output folder before and after test
@pytest.fixture(autouse=True)
def clean_output_files(test_move_inputs):
    # Delete copied over test files after test
    yield
    input_path = PROJECT_DIR / "tests/test_data/input_compile_notices"
    for filename in os.listdir(input_path):
        if not os.path.exists(OUTPUT_DIR / filename):
            print(f"File {filename} not found in output folder.")
        else:
            if OUTPUT_DIR / filename not in test_move_inputs:
                print(f"Cleaning file {filename} from output folder.")
                (OUTPUT_DIR / filename).unlink()
            else:
                print(f"Not removing file {filename} from output folder.")


def extract_client_id(text):
    match = re.search(r"Client ID:\s*(\d+)", text)
    return match.group(1) if match else None


# Run tests for Compile Notices step of pipeline
def test_compile_notices(test_school_batch_names, test_move_inputs):
    # Set working directory to scripts
    working_dir = PROJECT_DIR / "scripts"

    # Run the script
    script_path = PROJECT_DIR / "scripts" / "compile_notices.sh"

    result = subprocess.run(
        [script_path, TEST_LANG], cwd=working_dir, capture_output=True, text=True
    )

    assert result.returncode == 0, f"Script failed: {result.stderr}"

    # Check that .pdf files were created for each school batch
    for test_school_batch_name in test_school_batch_names:
        filepath = OUTPUT_DIR / (test_school_batch_name + "_immunization_notice.pdf")

        # Check that .pdf file exists
        assert os.path.exists(filepath), (
            f"Missing pdf: {test_school_batch_name}_immunization_notice.pdf"
        )

        # Check that file is not empty
        assert os.path.getsize(filepath) != 0, (
            f"Empty pdf: {test_school_batch_name}_immunization_notice.pdf"
        )

        # Read file
        reader = PdfReader(str(filepath))

        assert len(reader.pages) > 0, (
            f"{test_school_batch_name}_immunization_notice.pdf has no pages"
        )

        pages = [page.extract_text() or "" for page in reader.pages]

        assert "".join(pages).strip(), (
            f"{test_school_batch_name}_immunization_notice.pdf is empty or has no readable text"
        )

        client_sections = {}
        current_client = None

        for i, text in enumerate(pages):
            found_id = extract_client_id(text)
            if found_id:
                current_client = found_id
                client_sections[current_client] = [i]
            elif current_client:
                client_sections[current_client].append(i)

        # Validate each client's section
        for client_id, page_indices in client_sections.items():
            print(len(page_indices))
            assert len(page_indices) <= 2, f"{client_id} has more than 2 pages"
            assert page_indices == sorted(page_indices), (
                f"{client_id}'s pages are not consecutive"
            )

        # Check that all clients are present in pdf
        client_id_list = pd.read_csv(
            OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv"),
            header=None,
            names=["client_ids"],
        )

        for client_id in client_id_list["client_ids"]:
            assert str(client_id) in client_sections.keys()

        # Remove test output file
        filepath.unlink()
