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
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"
BATCH_SIZE = 100 # Make sure this matches preprocess.py value

@pytest.fixture
def test_input_path():
    return INPUT_DIR / "test_dataset.xlsx"


@pytest.fixture
def test_move_inputs():
    input_path = PROJECT_DIR / "tests/test_data/input_run_pipeline"
    filename = "test_dataset.xlsx"

    if not os.path.exists(INPUT_DIR / filename):
        print(f"File {filename} not found at destination. Copying from test directory...")
        shutil.copy(input_path / filename, INPUT_DIR / filename)
    else:
        print(f"File {filename} already exists at destination.")


@pytest.fixture(autouse=True)
def clean_output_files(test_input_path):
    input_exts = ["*.typ", "*.csv", "*.json", "*.pdf"]
    # Delete confounding files before the test
    for ext in input_exts:
        if OUTPUT_DIR.exists():
            for typ_file in OUTPUT_DIR.glob(ext):
                typ_file.unlink()
    yield
    # Delete confounding files after the test
    output_exts = ["*.typ", "*.csv", "*.json", "*.pdf"]
    for ext in output_exts:
        if OUTPUT_DIR.exists():
            for typ_file in OUTPUT_DIR.glob(ext):
                typ_file.unlink()
    # Delete directories generated during script
    gen_dirs = ['batches', 'by_school', f'json_{TEST_LANG}']
    for gen_dir in gen_dirs:
        dir_path = PROJECT_DIR / f"output/{gen_dir}"
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"Directory '{dir_path}' and all its contents deleted successfully.")
        else:
            print(f"Directory '{dir_path}' does not exist.")

    # Delete copied input file
    if os.path.exists(test_input_path):
        test_input_path.unlink()


def extract_client_id(text):
    match = re.search(r"Client ID:\s*(\d+)", text)
    return match.group(1) if match else None

def test_run_pipeline_with_real_data(test_input_path, test_move_inputs, clean_output_files):

    test_df = pd.read_excel(test_input_path)

    test_school_batch_names = []

    for school_name in test_df["School Name"].unique():
        num_batches = math.ceil(len(test_df[test_df["School Name"] == school_name]) / BATCH_SIZE)
        for num_batch in range(num_batches):
            test_school_batch_name = f"{school_name.replace(' ', '_').upper()}_{(num_batch + 1):0{2}d}"
            test_school_batch_names.append(test_school_batch_name)
    
    script_path = PROJECT_DIR / "scripts" / "run_pipeline.sh"

    # Set working directory to project root (two levels up from test file)
    working_dir = PROJECT_DIR / "scripts"

    # Run the script
    result = subprocess.run(
        [script_path, test_input_path.name, TEST_LANG, "--no-cleanup"],
        cwd=working_dir,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Script failed: {result.stderr}"

    # Check that .pdf files were created for each school batch
    for test_school_batch_name in test_school_batch_names:
        filepath = OUTPUT_DIR / (test_school_batch_name + "_immunization_notice.pdf")

        # Check that .pdf file exists
        assert os.path.exists(filepath), f"Missing pdf: {test_school_batch_name}_immunization_notice.pdf"

        # Check that file is not empty
        assert os.path.getsize(filepath) != 0, f"Empty pdf: {test_school_batch_name}_immunization_notice.pdf"

        # Read file
        
        reader = PdfReader(str(filepath))

        
        assert len(reader.pages) > 0, f"{test_school_batch_name}_immunization_notice.pdf has no pages"

        pages = [page.extract_text() or "" for page in reader.pages]

        assert "".join(pages).strip(), f"{test_school_batch_name}_immunization_notice.pdf is empty or has no readable text"

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
            assert page_indices == sorted(page_indices), f"{client_id}'s pages are not consecutive"

        # Check that all clients are present in pdf
        client_id_list = pd.read_csv(OUTPUT_DIR / (test_school_batch_name + "_client_ids.csv"), header=None, names=['client_ids'])
        for client_id in client_id_list['client_ids']:
            assert str(client_id) in client_sections.keys()



