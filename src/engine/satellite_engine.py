import os
import sys
import json
import time
import sqlite3
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from pystac_client import Client
import planetary_computer

DB_PATH = "data/database/terrascope.db"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

def init_sat_table(conn):
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS satellite_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ramsar_id INTEGER NOT NULL,
            target_year INTEGER NOT NULL,
            scene_id TEXT NOT NULL,
            acquisition_date TEXT NOT NULL,
            cloud_cover_pct REAL,
            valid_pixels INTEGER,
            water_ratio_pct REAL,
            vegetation_ratio_pct REAL,
            dry_or_barren_ratio_pct REAL,
            mean_ndwi REAL,
            mean_ndvi REAL,
            sample_bbox_wgs84 TEXT,
            processing_time_sec REAL,
            status TEXT NOT NULL,
            UNIQUE(ramsar_id, target_year)
        )
    ''')
    conn.commit()

def get_sample_window_bbox(lat, lon, half_deg=0.045):
    return [
        round(lon - half_deg, 5),
        round(lat - half_deg, 5),
        round(lon + half_deg, 5),
        round(lat + half_deg, 5)
    ]

def analyze_wetland_year(catalog, ramsar_id, lat, lon, year):
    t0 = time.time()
    sample_bbox = get_sample_window_bbox(lat, lon, half_deg=0.045)
    date_range = f"{year}-08-01/{year}-10-20"

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=sample_bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": 18}}
    )
    items = list(search.items())
    if not items:
        return None

    items.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100.0))
    best_item = planetary_computer.sign(items[0])

    scene_id = best_item.id
    acq_date = best_item.datetime.strftime("%Y-%m-%d")
    cloud_cov = float(best_item.properties.get("eo:cloud_cover", 0.0))

    b03_href = best_item.assets["B03"].href
    b04_href = best_item.assets["B04"].href
    b08_href = best_item.assets["B08"].href

    with rasterio.open(b03_href) as src_green:
        crs_bounds = transform_bounds("EPSG:4326", src_green.crs, *sample_bbox)
        win = from_bounds(*crs_bounds, transform=src_green.transform)
        out_h = max(int(win.height // 2), 64)
        out_w = max(int(win.width // 2), 64)
        green = src_green.read(1, window=win, out_shape=(out_h, out_w)).astype(np.float32)

    with rasterio.open(b04_href) as src_red:
        red = src_red.read(1, window=win, out_shape=(out_h, out_w)).astype(np.float32)

    with rasterio.open(b08_href) as src_nir:
        nir = src_nir.read(1, window=win, out_shape=(out_h, out_w)).astype(np.float32)

    valid_mask = (green > 0) & (red > 0) & (nir > 0)
    valid_count = int(np.sum(valid_mask))
    if valid_count == 0:
        return None

    g_val = green[valid_mask]
    r_val = red[valid_mask]
    n_val = nir[valid_mask]

    ndwi = (g_val - n_val) / (g_val + n_val + 1e-6)
    ndvi = (n_val - r_val) / (n_val + r_val + 1e-6)

    # Salt-crust & bright playa filter: crystalline salt has extremely high Red & Green reflectance (DN > 3200 in L2A BOA)
    bright_salt_or_cloud = (r_val > 3200) & (g_val > 3200)

    # True open water has NDWI > 0.05 and is not hyper-reflective crystalline salt crust
    water_mask = (ndwi > 0.05) & (~bright_salt_or_cloud)
    veg_mask = (~water_mask) & (~bright_salt_or_cloud) & (ndvi > 0.22)
    dry_mask = (~water_mask) & (~veg_mask)

    water_pct = round(float(np.sum(water_mask)) / valid_count * 100.0, 2)
    veg_pct = round(float(np.sum(veg_mask)) / valid_count * 100.0, 2)
    dry_pct = round(float(np.sum(dry_mask)) / valid_count * 100.0, 2)

    mean_ndwi = round(float(np.mean(ndwi)), 4)
    mean_ndvi = round(float(np.mean(ndvi)), 4)
    dt = round(time.time() - t0, 2)

    return {
        "ramsar_id": ramsar_id,
        "target_year": year,
        "scene_id": scene_id,
        "acquisition_date": acq_date,
        "cloud_cover_pct": round(cloud_cov, 2),
        "valid_pixels": valid_count,
        "water_ratio_pct": water_pct,
        "vegetation_ratio_pct": veg_pct,
        "dry_or_barren_ratio_pct": dry_pct,
        "mean_ndwi": mean_ndwi,
        "mean_ndvi": mean_ndvi,
        "sample_bbox_wgs84": json.dumps(sample_bbox),
        "processing_time_sec": dt,
        "status": "OBSERVED_VALID"
    }

def update_wetland_observations(ramsar_id, years=None):
    if years is None:
        years = [2018, 2021, 2024]
    conn = sqlite3.connect(DB_PATH)
    init_sat_table(conn)
    cur = conn.cursor()
    cur.execute("SELECT name_en, name_fa, latitude, longitude FROM wetlands WHERE ramsar_id = ?", (ramsar_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"error": f"Wetland {ramsar_id} not found"}

    name_en, name_fa, lat, lon = row
    catalog = Client.open(STAC_URL)
    results = []
    for yr in years:
        res = analyze_wetland_year(catalog, ramsar_id, lat, lon, yr)
        if res:
            cur.execute('''
                INSERT OR REPLACE INTO satellite_observations (
                    ramsar_id, target_year, scene_id, acquisition_date, cloud_cover_pct,
                    valid_pixels, water_ratio_pct, vegetation_ratio_pct, dry_or_barren_ratio_pct,
                    mean_ndwi, mean_ndvi, sample_bbox_wgs84, processing_time_sec, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                res["ramsar_id"], res["target_year"], res["scene_id"], res["acquisition_date"],
                res["cloud_cover_pct"], res["valid_pixels"], res["water_ratio_pct"],
                res["vegetation_ratio_pct"], res["dry_or_barren_ratio_pct"],
                res["mean_ndwi"], res["mean_ndvi"], res["sample_bbox_wgs84"],
                res["processing_time_sec"], res["status"]
            ))
            conn.commit()
            results.append(res)
    conn.close()
    return {"ramsar_id": ramsar_id, "name_en": name_en, "name_fa": name_fa, "observations": results}

if __name__ == "__main__":
    target_ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [38, 40, 53]
    for rid in target_ids:
        out = update_wetland_observations(rid, years=[2018, 2024])
        print(json.dumps(out, ensure_ascii=False))
