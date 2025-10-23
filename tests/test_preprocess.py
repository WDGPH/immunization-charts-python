import pytest
from scripts.preprocess import (
    ClientDataProcessor,
    split_batches,
    load_data,
    validate_transform_columns,
    separate_by_school,
)
import pandas as pd
import os
from pathlib import Path
import logging
import json
import math
import shutil

TEST_LANG = "english"
PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_DIR / "input"
OUTPUT_DIR = PROJECT_DIR / f"output/json_{TEST_LANG}"
BATCH_SIZE = 2
TEST_DATASET = "test_dataset.xlsx"


# Copy test data to temporary dir
@pytest.fixture
def sample_data(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    input_path = PROJECT_DIR / "tests/test_data/input_preprocess"
    filename = TEST_DATASET

    if not os.path.exists(input_dir / filename):
        print(
            f"File {filename} not found at destination. Copying from test directory..."
        )
        shutil.copy(input_path / filename, input_dir / filename)
    else:
        print(f"File {filename} already exists at destination.")

    return tmp_path


def test_load_data(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    sample_files.append(input_path)

    df = load_data(input_path)

    # Test load_data
    assert not df.empty


def test_validate_transform_columns(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    sample_files.append(input_path)

    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
        "AGE",
    ]

    df = load_data(input_path)

    # Test validate_transform_columns
    validate_transform_columns(
        df, required_columns
    )  # FIXME make required_columns come from a config file

    for column in required_columns:
        column = column.replace(" ", "_")
        column = column.replace("PROVINCE/TERRITORY", "PROVINCE")
        assert column in df.columns


def test_separate_by_school(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    output_dir = tmp_dir / "output"

    output_dir_school = output_dir / "by_school"

    sample_files.append(input_path)

    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
        "AGE",
    ]

    df = load_data(input_path)

    # Test validate_transform_columns
    validate_transform_columns(
        df, required_columns
    )  # FIXME make required_columns come from a config file

    # Test separate_by_school
    separate_by_school(df, output_dir_school, "SCHOOL_NAME")

    for school_name in df["SCHOOL_NAME"].unique():
        assert os.path.exists(
            output_dir_school / f"{school_name.replace(' ', '_').upper()}.csv"
        )


def test_split_batches(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    output_dir = tmp_dir / "output"

    output_dir_school = output_dir / "by_school"
    output_dir_batch = output_dir / "batches"

    sample_files.append(input_path)

    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
        "AGE",
    ]

    df = load_data(input_path)

    # Test validate_transform_columns
    validate_transform_columns(
        df, required_columns
    )  # FIXME make required_columns come from a config file

    # Test separate_by_school
    separate_by_school(df, output_dir_school, "SCHOOL_NAME")

    # Test split_batches
    batch_dir = Path(output_dir_batch)
    split_batches(Path(output_dir_school), batch_dir, BATCH_SIZE)
    logging.info("Completed splitting into batches.")

    for school_name in df["SCHOOL_NAME"].unique():
        num_batches = math.ceil(len(df[df["SCHOOL_NAME"] == school_name]) / BATCH_SIZE)
        for num_batch in range(num_batches):
            assert os.path.exists(
                output_dir_batch
                / f"{school_name.replace(' ', '_').upper()}_{(num_batch + 1):0{2}d}.csv"
            )


def test_batch_processing(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    output_dir = tmp_dir / "output"
    language = "english"

    output_dir_school = output_dir / "by_school"
    output_dir_batch = output_dir / "batches"

    sample_files.append(input_path)

    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "AGE",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
        "AGE",
    ]

    df = load_data(input_path)

    # Test validate_transform_columns
    validate_transform_columns(
        df, required_columns
    )  # FIXME make required_columns come from a config file

    # Test separate_by_school
    separate_by_school(df, output_dir_school, "SCHOOL_NAME")

    # Test split_batches
    batch_dir = Path(output_dir_batch)
    split_batches(Path(output_dir_school), batch_dir, BATCH_SIZE)
    logging.info("Completed splitting into batches.")

    all_batch_files = sorted(batch_dir.glob("*.csv"))

    # Test batch processing
    assert os.path.exists("./config/disease_map.json")
    assert os.path.exists("./config/vaccine_reference.json")

    for batch_file in all_batch_files:
        print(f"Processing batch file: {batch_file}")
        df_batch = pd.read_csv(
            batch_file, sep=";", engine="python", encoding="latin-1", quotechar='"'
        )

        if "STREET_ADDRESS_LINE_2" in df_batch.columns:
            df_batch["STREET_ADDRESS"] = (
                df_batch["STREET_ADDRESS_LINE_1"].fillna("")
                + " "
                + df_batch["STREET_ADDRESS_LINE_2"].fillna("")
            )
            df_batch.drop(
                columns=["STREET_ADDRESS_LINE_1", "STREET_ADDRESS_LINE_2"], inplace=True
            )

        processor = ClientDataProcessor(
            df=df_batch,
            disease_map=json.load(open("./config/disease_map.json")),
            vaccine_ref=json.load(open("./config/vaccine_reference.json")),
            ignore_agents=[
                "-unspecified",
                "unspecified",
                "Not Specified",
                "Not specified",
                "Not Specified-unspecified",
            ],
            delivery_date="2024-06-01",
            language=language,  # or 'french'
        )
        processor.build_notices()
        logging.info("Preprocessing completed successfully.")

        assert len(processor.notices) == len(df_batch)


def test_save_output(sample_data):
    sample_files = []

    tmp_dir = sample_data

    input_dir = tmp_dir / "input"
    input_path = input_dir / TEST_DATASET

    output_dir = tmp_dir / "output"
    language = "english"

    output_dir_school = output_dir / "by_school"
    output_dir_final = output_dir / ("json_" + language)
    output_dir_batch = output_dir / "batches"

    sample_files.append(input_path)

    required_columns = [
        "SCHOOL NAME",
        "CLIENT ID",
        "FIRST NAME",
        "LAST NAME",
        "DATE OF BIRTH",
        "CITY",
        "POSTAL CODE",
        "PROVINCE/TERRITORY",
        "AGE",
        "OVERDUE DISEASE",
        "IMMS GIVEN",
        "STREET ADDRESS LINE 1",
        "STREET ADDRESS LINE 2",
        "AGE",
    ]

    df = load_data(input_path)

    # Test validate_transform_columns
    validate_transform_columns(
        df, required_columns
    )  # FIXME make required_columns come from a config file

    # Test separate_by_school
    separate_by_school(df, output_dir_school, "SCHOOL_NAME")

    # Test split_batches
    batch_dir = Path(output_dir_batch)
    split_batches(Path(output_dir_school), batch_dir, BATCH_SIZE)
    logging.info("Completed splitting into batches.")

    all_batch_files = sorted(batch_dir.glob("*.csv"))

    # Test batch processing

    for batch_file in all_batch_files:
        print(f"Processing batch file: {batch_file}")
        df_batch = pd.read_csv(
            batch_file, sep=";", engine="python", encoding="latin-1", quotechar='"'
        )

        if "STREET_ADDRESS_LINE_2" in df_batch.columns:
            df_batch["STREET_ADDRESS"] = (
                df_batch["STREET_ADDRESS_LINE_1"].fillna("")
                + " "
                + df_batch["STREET_ADDRESS_LINE_2"].fillna("")
            )
            df_batch.drop(
                columns=["STREET_ADDRESS_LINE_1", "STREET_ADDRESS_LINE_2"], inplace=True
            )

        processor = ClientDataProcessor(
            df=df_batch,
            disease_map=json.load(open("./config/disease_map.json")),
            vaccine_ref=json.load(open("./config/vaccine_reference.json")),
            ignore_agents=[
                "-unspecified",
                "unspecified",
                "Not Specified",
                "Not specified",
                "Not Specified-unspecified",
            ],
            delivery_date="2024-06-01",
            language=language,  # or 'french'
        )
        processor.build_notices()
        processor.save_output(Path(output_dir_final), batch_file.stem)
        logging.info("Preprocessing completed successfully.")

    # Test save_output
    for school_name in df["SCHOOL_NAME"].unique():
        num_batches = math.ceil(len(df[df["SCHOOL_NAME"] == school_name]) / BATCH_SIZE)
        for num_batch in range(num_batches):
            assert os.path.exists(
                output_dir_final
                / f"{school_name.replace(' ', '_').upper()}_{(num_batch + 1):0{2}d}.json"
            )
