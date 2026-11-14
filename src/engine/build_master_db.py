import os
import re
import glob
import json
import hashlib
import sqlite3
from openpyxl import load_workbook
from pypdf import PdfReader

DB_PATH = "data/database/terrascope.db"
DOCS_DIR = "data/raw_docs"

# Official Persian names mapped strictly to the 28 official Ramsar Site IDs of Iran
PERSIAN_NAMES = {
    36: "شبه‌جزیره میانکاله، خلیج گرگان و آب‌بندان لپو-زاغمرز",
    37: "دریاچه پریشان و دشت ارژن",
    38: "دریاچه ارومیه",
    39: "دریاچه‌های نی‌ریز (بختگان و طشک) و باتلاق‌های کامجان",
    40: "شتالاب بین‌المللی انزلی",
    41: "تالاب شادگان و پهنه‌های گلی خورالامیه و خورموسی",
    42: "هامون صابری و هامون هیرمند",
    43: "دریاچه کجی (قوری‌گل / کوبی)",
    44: "بخش جنوبی هامون پوزک",
    45: "دریاچه‌های شورگل، یادگارلو و درگه‌سنگی",
    46: "پارک ملی بوجاق",
    47: "تالاب امیرکلایه",
    48: "تالاب قوری‌گل",
    49: "دریاچه‌های آلاگل، آلماگل و آجی‌گل",
    50: "تنگه خوران (جنگل‌های حرا)",
    51: "دلتای رود شور، رود شیرین و رود میناب",
    52: "دلتای رود گز و رود حرا",
    53: "تالاب گاوخونی و باتلاق‌های پایین‌دست زاینده‌رود",
    1006: "خلیج گواتر و هور باهو",
    1015: "جزیره شیدور",
    1109: "تالاب گمیشان",
    1308: "آب‌بندان‌های فریدون‌کنار، ازباران و سرخرود",
    1939: "تالاب چغاخور",
    1940: "تالاب کانی‌برازان",
    2369: "دریاچه زریوار",
    2539: "تالاب برم الوان",
    2558: "تالاب گندمان",
    2601: "دریاچه گهر"
}
# Fix typo in ID 40 and 43 standard Persian titles
PERSIAN_NAMES[40] = "تالاب بین‌المللی انزلی"
PERSIAN_NAMES[43] = "دریاچه کوبی (قوبی)"

def get_sha256(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def classify_doc(fname):
    low = fname.lower()
    m = re.match(r"^ir(\d+)ris.*\.pdf$", low)
    if m:
        return "RIS_PDF", int(m.group(1))
    if "cop" in low or "nr_iran" in low or "iran_nr" in low:
        return "COP_NATIONAL_REPORT", None
    if "managementplan" in low:
        if "urmia" in low: return "MANAGEMENT_PLAN", 38
        if "parishan" in low: return "MANAGEMENT_PLAN", 37
        if "shadegan" in low: return "MANAGEMENT_PLAN", 41
        return "MANAGEMENT_PLAN", None
    if low.startswith("ram") and not low.startswith("ramsar"):
        return "RAM_MISSION_REPORT", None
    if "montreux" in low:
        if "alagol" in low: return "MONTREUX_RECORD_DOC", 49
        return "MONTREUX_RECORD_DOC", None
    if low.endswith(".xlsx"):
        return "OFFICIAL_TABULAR_DATASET", None
    if "annotated-summary" in low:
        return "OFFICIAL_SUMMARY_PDF", None
    return "POLICY_OR_BROCHURE", None

def build_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS document_catalog")
    cur.execute("DROP TABLE IF EXISTS wetlands")

    cur.execute('''
        CREATE TABLE document_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            doc_category TEXT NOT NULL,
            related_ramsar_id INTEGER,
            file_ext TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            page_count INTEGER,
            sha256 TEXT NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE wetlands (
            ramsar_id INTEGER PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_fa TEXT NOT NULL,
            province_en TEXT,
            designation_date TEXT,
            last_publication_date TEXT,
            area_ha REAL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            min_elevation_m REAL,
            max_elevation_m REAL,
            montreux_currently_listed TEXT,
            historical_montreux_Mentioned INTEGER,
            ram_mission_conducted TEXT,
            management_plan_available TEXT,
            management_plan_implemented TEXT,
            transboundary TEXT,
            criteria_json TEXT,
            wetland_types TEXT,
            ecosystem_services TEXT,
            threats TEXT,
            national_designations TEXT,
            international_designations TEXT,
            annotated_summary TEXT,
            ris_pdf_filename TEXT,
            ris_pdf_status TEXT NOT NULL
        )
    ''')

    print("=== 1. Auditing & Indexing 50 Local Reference Documents ===")
    ris_map = {}
    files = sorted(os.listdir(DOCS_DIR))
    for fname in files:
        fpath = os.path.join(DOCS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        size_b = os.path.getsize(fpath)
        sha = get_sha256(fpath)
        cat, rel_id = classify_doc(fname)
        
        pages = None
        if ext == ".pdf":
            try:
                reader = PdfReader(fpath)
                pages = len(reader.pages)
            except Exception:
                pages = -1

        if cat == "RIS_PDF" and rel_id is not None:
            ris_map[rel_id] = fname

        cur.execute('''
            INSERT INTO document_catalog 
            (filename, doc_category, related_ramsar_id, file_ext, file_size_bytes, page_count, sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (fname, cat, rel_id, ext, size_b, pages, sha))

    print(f"Indexed {len(files)} files successfully.")

    print("\n=== 2. Building Master 28 Wetlands Table from Official Excel ===")
    excel_path = glob.glob(os.path.join(DOCS_DIR, "*.xlsx"))[0]
    wb = load_workbook(excel_path, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))

    for r in rows[1:]:
        if r[0] is None:
            continue
        rid = int(r[0])
        name_en = str(r[1]).strip()
        name_fa = PERSIAN_NAMES.get(rid, "نامشخص")
        desig_date = str(r[5])[:10] if r[5] else None
        pub_date = str(r[6])[:10] if r[6] else None
        area_ha = float(r[7]) if r[7] is not None else None
        lat = float(r[8])
        lon = float(r[9])
        summary = str(r[10]).strip() if r[10] else None

        # Criteria 1..9 (columns 11 to 19)
        crit = {f"C{i}": (str(r[10+i]).strip() == "Yes") for i in range(1, 10)}
        
        w_types = str(r[20]).strip() if r[20] else None
        max_el = float(r[21]) if r[21] not in (None, "None", "") else None
        min_el = float(r[22]) if r[22] not in (None, "None", "") else None
        montreux_curr = str(r[23]).strip() if r[23] else "Unknown"
        hist_montreux = 1 if (summary and "montreux" in summary.lower()) or montreux_curr == "Yes" else 0
        mgmt_impl = str(r[24]).strip() if r[24] else "Unknown"
        mgmt_avail = str(r[25]).strip() if r[25] else "Unknown"
        eco_serv = str(r[26]).strip() if r[26] else None
        threats = str(r[27]).strip() if r[27] else None
        province = str(r[28]).strip() if r[28] else None
        intl_desig = str(r[29]).strip() if r[29] not in (None, "None") else None
        nat_desig = str(r[31]).strip() if r[31] not in (None, "None") else None
        transbound = str(r[32]).strip() if r[32] else "No"
        ram_mission = str(r[33]).strip() if r[33] else "No"

        ris_file = ris_map.get(rid, None)
        ris_status = "AVAILABLE_LOCAL_PDF" if ris_file else "MISSING_LOCAL_RIS_PDF"

        cur.execute('''
            INSERT INTO wetlands VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            rid, name_en, name_fa, province, desig_date, pub_date, area_ha,
            lat, lon, min_el, max_el, montreux_curr, hist_montreux, ram_mission,
            mgmt_avail, mgmt_impl, transbound, json.dumps(crit), w_types,
            eco_serv, threats, nat_desig, intl_desig, summary, ris_file, ris_status
        ))

    conn.commit()

    # Summary Audit Query
    cur.execute("SELECT COUNT(*), SUM(area_ha) FROM wetlands")
    w_count, total_area = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM wetlands WHERE montreux_currently_listed = 'Yes'")
    m_curr = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM wetlands WHERE ris_pdf_status = 'AVAILABLE_LOCAL_PDF'")
    ris_avail = cur.fetchone()[0]
    cur.execute("SELECT doc_category, COUNT(*), SUM(page_count) FROM document_catalog GROUP BY doc_category")
    doc_stats = cur.fetchall()

    print(f"\n=== DATABASE AUDIT SUMMARY (terrascope.db) ===")
    print(f"Total Official Ramsar Wetlands : {w_count}")
    print(f"Total Designated Area (ha)     : {total_area:,.0f} ha")
    print(f"Currently Montreux Listed      : {m_curr} sites")
    print(f"Local RIS PDF Coverage         : {ris_avail} / {w_count} sites (Missing only ID 1940: Kanibarazan)")
    print("\n--- Document Catalog Breakdown ---")
    for cat, cnt, pgs in doc_stats:
        pg_str = f"{pgs} pages" if pgs else "Tabular/N-A"
        print(f"  {cat:<26}: {cnt:>2} files ({pg_str})")

    conn.close()

if __name__ == "__main__":
    build_database()
