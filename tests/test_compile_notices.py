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
TEST_OUTPUT_DIR = PROJECT_DIR / "tests/test_data/input_compile_notices"
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"
TMP_TEST_DIR = PROJECT_DIR / "tests/tmp_test_dir/test_compile_notices_tmp"


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


def extract_client_id(text):
    match = re.search(r"Client ID:\s*(\d+)", text)
    return match.group(1) if match else None


# Run tests for Compile Notices step of pipeline
def test_compile_notices(test_school_batch_names):
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
