import os
import glob
import re
import sqlite3
from openpyxl import load_workbook

DB_PATH = "data/database/terrascope.db"
DOCS_DIR = "data/raw_docs"

def inspect_and_rebuild():
    excel_files = glob.glob(os.path.join(DOCS_DIR, "*.xlsx"))
    if not excel_files:
        print("ERROR: No Excel file found.")
        return
    
    wb = load_workbook(excel_files[0], data_only=True)
    sheet = wb.active
    
    rows = list(sheet.iter_rows(values_only=True))
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    
    print("=== Exact Columns in Official Ramsar Excel ===")
    for idx, h in enumerate(headers):
        print(f"  [{idx}] {h}")
        
    print(f"\nTotal data rows found: {len(rows) - 1}")
    if len(rows) > 1:
        print("\n=== Sample Row 1 Data ===")
        for idx, val in enumerate(rows[1]):
            print(f"  [{idx}] {headers[idx]}: {val}")

    # Map existing IR<id>RIS*.pdf files in raw_docs
    ris_files = {}
    for f in os.listdir(DOCS_DIR):
        m = re.match(r"^IR(\d+)RIS.*\.pdf$", f, re.IGNORECASE)
        if m:
            ris_files[int(m.group(1))] = f

    print(f"\nFound {len(ris_files)} dedicated RIS PDF files in raw_docs.")
    
    # Check which Ramsar IDs from Excel have/don't have RIS PDFs
    print("\n=== Verifying Ramsar IDs against RIS PDFs ===")
    for r in rows[1:]:
        if r[0] is not None:
            try:
                rid = int(r[0])
                has_pdf = ris_files.get(rid, "MISSING_IN_LOCAL_DOCS")
                print(f"  Ramsar ID {rid:<5} | Name: {str(r[1]):<42} | RIS PDF: {has_pdf}")
            except ValueError:
                print(f"  Non-integer row ID: {r[0]}")

if __name__ == "__main__":
    inspect_and_rebuild()
