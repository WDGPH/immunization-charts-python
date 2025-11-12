from rapidfuzz import fuzz, process
import pandas as pd
import argparse
import sys

# Required canonical names for use in the pipeline
REQUIRED_COLUMNS = [
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
    "STREET ADDRESS LINE 2"
]

def normalize(col: str) -> str:
    """Normalize formatting prior to matching."""
    return col.lower().strip().replace(" ", "_").replace("-", "_")


def map_columns(df: pd.DataFrame, required_columns=REQUIRED_COLUMNS):
    input_cols = df.columns
    col_map = {}

    # Normalize input columns for matching
    normalized_input_cols = [normalize(c) for c in input_cols]

    # Check each input column against required columns
    for input_col in normalized_input_cols:
        
        col_name, score, index = process.extractOne(
            query=input_col,
            choices=[normalize(req) for req in required_columns],
            scorer=fuzz.partial_ratio
        )

        # Remove column if it has a score of 0
        best_match = required_columns[index]

        if score >= 80:  # adjustable threshold
            # Map the original column name, not the normalized one
            actual_in_col = next(c for c in input_cols if normalize(c) == input_col)
            col_map[actual_in_col] = best_match

            # print colname and score for debugging
            print(f"Matching '{input_col}' to '{best_match}' with score {score}")
        
    return df.rename(columns=col_map), col_map

def filter_columns(
    df: pd.DataFrame, required_columns: list[str] = REQUIRED_COLUMNS
) -> pd.DataFrame:
    """Filter dataframe to only include required columns."""
    if df is None or df.empty:
        return df

    return df[[col for col in df.columns if col in required_columns]]

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Map and filter dataframe columns to required canonical names."
    )
    parser.add_argument("input_path", help="Path to input Excel or CSV file")
    args = parser.parse_args()

    input_path = args.input_path
    try:
        if input_path.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(input_path)
        elif input_path.lower().endswith(".csv"):
            df = pd.read_csv(input_path)
        else:
            raise ValueError("Unsupported file type. Provide .csv, .xls or .xlsx")
    except Exception as exc:  
        print(f"Error reading file '{input_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    if df is None or df.empty:
        print("No data loaded or file is empty.", file=sys.stderr)
        sys.exit(0)

    normalized_columns = [normalize(col) for col in df.columns]
    print("Normalized Columns:", normalized_columns)

    mapped_df, column_mapping = map_columns(df)
    filtered_df = filter_columns(mapped_df)

    # Show a concise preview of the result
    print("Column mapping:", column_mapping)