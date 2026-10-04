import csv
from pathlib import Path

raw_folder = Path(__file__).parent / "data" / "raw"

for file in sorted(raw_folder.glob("*.csv")):
    with file.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        columns = next(reader)
        row_count = sum(1 for _ in reader)

    print(f"\nFILE: {file.name}")
    print(f"ROWS: {row_count:,}")
    print(f"COLUMNS: {', '.join(columns)}")