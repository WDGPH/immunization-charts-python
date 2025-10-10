#!/usr/bin/env python3
import sys
import pandas as pd
from pathlib import Path

def count_records(filepath):
    path = Path(filepath)
    if not path.exists():
        print(0)
        return
    suffix = path.suffix.lower()
    if suffix in {'.xlsx', '.xls'}:
        df = pd.read_excel(path, engine="openpyxl")
    else:
        df = pd.read_csv(path)
    print(len(df.index))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: count_records.py <input_file>")
        sys.exit(1)
    count_records(sys.argv[1])
