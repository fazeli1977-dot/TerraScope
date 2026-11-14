import os
import sqlite3
import hashlib
import glob
from openpyxl import load_workbook

DB_PATH = "data/database/terrascope.db"
DOCS_DIR = "data/raw_docs"

def get_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def init_db():
    os.makedirs("data/database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS document_catalog')
    cursor.execute('DROP TABLE IF EXISTS wetlands')
    cursor.execute('''CREATE TABLE document_catalog (
                        id INTEGER PRIMARY KEY,
                        filename TEXT,
                        sha256 TEXT,
                        file_type TEXT)''')
    cursor.execute('''CREATE TABLE wetlands (
                        ramsar_id TEXT PRIMARY KEY,
                        name_en TEXT,
                        area_ha REAL,
                        designation_date TEXT,
                        coords TEXT)''')
    conn.commit()
    return conn

def ingest():
    conn = init_db()
    cursor = conn.cursor()
    
    # Ingest Files
    print("--- Cataloging Documents ---")
    files = glob.glob(os.path.join(DOCS_DIR, "*.*"))
    for f in files:
        ext = os.path.splitext(f)[1]
        fname = os.path.basename(f)
        h = get_sha256(f)
        cursor.execute("INSERT INTO document_catalog (filename, sha256, file_type) VALUES (?, ?, ?)", 
                       (fname, h, ext))
        print(f"Indexed: {fname}")

    # Ingest Excel Data
    excel_file = glob.glob(os.path.join(DOCS_DIR, "*.xlsx"))[0]
    print(f"\n--- Loading Wetland Data from {os.path.basename(excel_file)} ---")
    wb = load_workbook(excel_file, data_only=True)
    sheet = wb.active
    
    # Assuming standard Ramsar format (adjust indices based on header row)
    # We skip header row (index 0)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # row: [RamsarID, SiteName, Area, Date, ...]
        if row[0]: # Ensure ID exists
            cursor.execute("INSERT OR IGNORE INTO wetlands VALUES (?, ?, ?, ?, ?)", 
                           (str(row[0]), row[1], row[2], row[3], "0,0"))
            
    conn.commit()
    conn.close()
    print("SUCCESS: Database populated.")

if __name__ == "__main__":
    ingest()
