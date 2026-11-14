import os
import math
import json
import time
import sqlite3
import requests
from pypdf import PdfReader

DB_PATH = "data/database/terrascope.db"
DOCS_DIR = "data/raw_docs"
GEO_DIR = "data/cache/boundaries"

def compute_observation_bbox(lat, lon, area_ha):
    '''
    Computes a scientifically proportional observation bounding box [min_lon, min_lat, max_lon, max_lat]
    around the official Ramsar center coordinate based on official designated area (ha),
    with a minimum 5kmx5km window and maximum 30kmx30km window for fast Sentinel-2 windowed reading.
    '''
    area_km2 = max((area_ha or 1000.0) / 100.0, 25.0)
    side_km = min(max(math.sqrt(area_km2) * 1.4, 6.0), 30.0)
    half_km = side_km / 2.0
    
    d_lat = half_km / 111.32
    d_lon = half_km / (111.32 * math.cos(math.radians(lat)))
    
    return [
        round(lon - d_lon, 5),
        round(lat - d_lat, 5),
        round(lon + d_lon, 5),
        round(lat + d_lat, 5)
    ]

def run_extraction_and_geo():
    os.makedirs(GEO_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Create page-level text table and FTS5 full-text index
    cur.execute("DROP TABLE IF EXISTS document_pages")
    cur.execute("DROP TABLE IF EXISTS document_pages_fts")

    cur.execute('''
        CREATE TABLE document_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            doc_category TEXT NOT NULL,
            related_ramsar_id INTEGER,
            page_number INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES document_catalog(id)
        )
    ''')

    cur.execute('''
        CREATE VIRTUAL TABLE document_pages_fts USING fts5(
            filename,
            doc_category,
            page_number UNINDEXED,
            text_content
        )
    ''')

    print("=== 1. Extracting Page-Level Text from all 49 PDFs (916 Pages) ===")
    t0 = time.time()
    cur.execute("SELECT id, filename, doc_category, related_ramsar_id FROM document_catalog WHERE file_ext = '.pdf'")
    pdf_docs = cur.fetchall()

    total_pages_extracted = 0
    total_chars = 0

    for doc_id, fname, cat, rel_id in pdf_docs:
        fpath = os.path.join(DOCS_DIR, fname)
        try:
            reader = PdfReader(fpath)
            for idx, page in enumerate(reader.pages):
                pg_num = idx + 1
                txt = page.extract_text() or ""
                txt_clean = " ".join(txt.split())
                c_len = len(txt_clean)
                total_pages_extracted += 1
                total_chars += c_len

                cur.execute('''
                    INSERT INTO document_pages
                    (doc_id, filename, doc_category, related_ramsar_id, page_number, text_content, char_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (doc_id, fname, cat, rel_id, pg_num, txt_clean, c_len))

                cur.execute('''
                    INSERT INTO document_pages_fts (filename, doc_category, page_number, text_content)
                    VALUES (?, ?, ?, ?)
                ''', (fname, cat, pg_num, txt_clean))
        except Exception as e:
            print(f"  [WARN] Error reading {fname}: {e}")

    conn.commit()
    print(f"Extracted {total_pages_extracted} pages ({total_chars:,} characters) into SQLite FTS5 in {time.time() - t0:.2f}s.")

    # 2. Add bbox_json and boundary_status columns to wetlands if not present
    cur.execute("PRAGMA table_info(wetlands)")
    cols = [c[1] for c in cur.fetchall()]
    if "bbox_json" not in cols:
        cur.execute("ALTER TABLE wetlands ADD COLUMN bbox_json TEXT")
    if "boundary_geojson_status" not in cols:
        cur.execute("ALTER TABLE wetlands ADD COLUMN boundary_geojson_status TEXT")

    # Test RSIS Geoserver WFS availability for Iran sites (strictly read-only public check)
    print("\n=== 2. Testing Public RSIS GeoServer & Computing Observation BBoxes ===")
    rsis_wfs_url = "https://rsis.ramsar.org/geoserver/wfs"
    wfs_params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "ramsar_sdi:features_published",
        "CQL_FILTER": "iso3='IRN'",
        "outputFormat": "application/json"
    }
    rsis_features = {}
    try:
        r = requests.get(rsis_wfs_url, params=wfs_params, timeout=15)
        if r.status_code == 200 and "features" in r.text:
            data = r.json()
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                rid = props.get("ramsarid")
                if rid is not None:
                    rsis_features[int(rid)] = feat
            print(f"RSIS Public WFS responded: Retrieved {len(rsis_features)} official polygon features for Iran.")
        else:
            print(f"RSIS Public WFS status {r.status_code}: Using official Excel coordinates + proportional BBox.")
    except Exception as e:
        print(f"RSIS WFS check skipped/unavailable ({type(e).__name__}): Using official Excel coordinates + proportional BBox.")

    cur.execute("SELECT ramsar_id, latitude, longitude, area_ha FROM wetlands")
    for rid, lat, lon, area_ha in cur.fetchall():
        bbox = compute_observation_bbox(lat, lon, area_ha)
        if rid in rsis_features:
            geo_path = os.path.join(GEO_DIR, f"IR_{rid}_boundary.geojson")
            with open(geo_path, "w", encoding="utf-8") as gf:
                json.dump(rsis_features[rid], gf)
            b_status = "OFFICIAL_RSIS_POLYGON_CACHED"
        else:
            b_status = "PROPORTIONAL_BBOX_FROM_OFFICIAL_CENTROID"

        cur.execute('''
            UPDATE wetlands
            SET bbox_json = ?, boundary_geojson_status = ?
            WHERE ramsar_id = ?
        ''', (json.dumps(bbox), b_status, rid))

    conn.commit()

    # 3. Quick verification of FTS5 Search speed
    t1 = time.time()
    cur.execute('''
        SELECT filename, page_number, snippet(document_pages_fts, 3, '[', ']', '...', 18)
        FROM document_pages_fts
        WHERE document_pages_fts MATCH 'Montreux AND Anzali'
        LIMIT 3
    ''')
    hits = cur.fetchall()
    dt_ms = (time.time() - t1) * 1000.0
    print(f"\n=== 3. FTS5 Instant Citation Search Test ({dt_ms:.2f} ms) ===")
    for fn, pg, snip in hits:
        print(f"  -> {fn} (Page {pg}): {snip}")

    conn.close()

if __name__ == "__main__":
    run_extraction_and_geo()
