import subprocess
import pytest
from pathlib import Path
import os
from pypdf import PdfReader
import re
import pandas as pd
import math
import shutil

TEST_LANG = "english"
PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_DIR / "input"
TEST_INPUT_DIR = PROJECT_DIR / "tests/test_data/input_run_pipeline"
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"
BATCH_SIZE = 100  # Make sure this matches preprocess.py value
TMP_TEST_DIR = (
    PROJECT_DIR / "tests/tmp_test_dir/test_run_pipeline_tmp"
)  # Name of test dir where existing files in ./input and ./output will be stored


# Returns filepath for input dataset
@pytest.fixture
def test_input_path():
    return INPUT_DIR / "test_dataset.xlsx"


# Cleans output folder before and after test
@pytest.fixture(autouse=True)
def clean_output_files():
    filename = "test_dataset.xlsx"

    tmp_filenames = {}

    # Move existing input and output directories to temporary directory during testing
    if os.path.exists(PROJECT_DIR / "input"):
        print(f"Temporarily moving input folder to {TMP_TEST_DIR}/input")
        os.makedirs(TMP_TEST_DIR, exist_ok=True)
        shutil.move(PROJECT_DIR / "input", TMP_TEST_DIR / "input")
        tmp_filenames[PROJECT_DIR / "input"] = TMP_TEST_DIR / "input"

    if os.path.exists(PROJECT_DIR / "output"):
        print(f"Temporarily moving output folder to {TMP_TEST_DIR}/output")
        os.makedirs(TMP_TEST_DIR, exist_ok=True)
        shutil.move(PROJECT_DIR / "output", TMP_TEST_DIR / "output")
        tmp_filenames[PROJECT_DIR / "output"] = TMP_TEST_DIR / "output"

    # Move test input to input directory
    os.makedirs(INPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_DIR / filename):
        print(
            f"File {filename} not found at destination. Copying from test directory..."
        )
        shutil.copy(TEST_INPUT_DIR / filename, INPUT_DIR / filename)
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


# Run tests for whole pipeline
def test_run_pipeline(test_input_path, clean_output_files):
    test_df = pd.read_excel(test_input_path)

    test_school_batch_names = []
    test_school_names = []

    for school_name in test_df["School Name"].unique():
        test_school_names.append(f"{school_name.replace(' ', '_').upper()}")
        num_batches = math.ceil(
            len(test_df[test_df["School Name"] == school_name]) / BATCH_SIZE
        )
        for num_batch in range(num_batches):
            test_school_batch_name = (
                f"{school_name.replace(' ', '_').upper()}_{(num_batch + 1):0{2}d}"
            )
            test_school_batch_names.append(test_school_batch_name)

    # Set working directory to scripts
    working_dir = PROJECT_DIR / "scripts"

    # Run the script
    script_path = PROJECT_DIR / "scripts" / "run_pipeline.sh"

    result = subprocess.run(
        [script_path, test_input_path.name, TEST_LANG, "--no-cleanup"],
        cwd=working_dir,
        capture_output=True,
        text=True,
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

        # Check that client_id csv file exists for school batch
        assert os.path.exists(
            OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv")
        ), f"Missing csv: {test_school_batch_name}_client_ids.csv"
        assert (
            os.path.getsize(OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv"))
            != 0
        ), {f"Empty csv: {test_school_batch_name}_client_ids.csv"}

        # Check that all clients are present in pdf
        client_id_list = pd.read_csv(
            OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv"),
            header=None,
            names=["client_ids"],
        )
        for client_id in client_id_list["client_ids"]:
            assert str(client_id) in client_sections.keys()

        # Check that json file exists for school batch
        assert os.path.exists(OUTPUT_DIR / (test_school_batch_name + ".json")), (
            f"Missing json: {test_school_batch_name}.json"
        )
        assert os.path.getsize(OUTPUT_DIR / (test_school_batch_name + ".json")) != 0, {
            f"Empty json: {test_school_batch_name}.json"
        }

        # Check that immunization notice .typ file exists for school batch
        assert os.path.exists(
            OUTPUT_DIR / (test_school_batch_name + "_immunization_notice.typ")
        ), f"Missing .typ: {test_school_batch_name}_immunization_notice.typ"

        # Remove test output files in output/json_{lang} and output/batches folders
        filepath.unlink()
        (OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv")).unlink()
        (OUTPUT_DIR / (test_school_batch_name + ".json")).unlink()
        (OUTPUT_DIR / (test_school_batch_name + "_immunization_notice.typ")).unlink()

        (PROJECT_DIR / ("output/batches/" + test_school_batch_name + ".csv")).unlink()

        if os.path.exists(OUTPUT_DIR / "conf.typ"):
            (OUTPUT_DIR / "conf.typ").unlink()

        if os.path.exists(OUTPUT_DIR / "conf.pdf"):
            (OUTPUT_DIR / "conf.pdf").unlink()

    # Remove test outputs in output/by_school folder
    for test_school_name in test_school_names:
        (PROJECT_DIR / ("output/by_school/" + test_school_name + ".csv")).unlink()
