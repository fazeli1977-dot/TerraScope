import os
import zipfile
import tempfile
import shutil
import json
import math
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import unary_union

# مسیرهای اصلی پروژه TerraScope
BASE_DIR = Path(r"C:\Projects\TerraScope")
RAW_DIR = BASE_DIR / "data" / "raw"
GEOJSON_DIR = BASE_DIR / "data" / "geojson"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

GEOJSON_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# پایگاه داده مرجع 28 تالاب رامسر ایران (استخراج‌شده از جدول رسمی RSIS کنوانسیون رامسر)
RAMSAR_SITES = [
    {"ramsar_id": 36, "name_en": "Miankaleh Peninsula, Gorgan Bay and Lapoo-Zaghmarz Ab-bandan", "name_fa": "شبه‌جزیره میانکاله، خلیج گرگان و آب‌بندان لپو زاغمرز", "lat": 36.827674, "lon": 53.697212, "area_ha": 100000.0, "elev_min": 0, "elev_max": 0, "montreux": False, "folder_hint": "miankaleh"},
    {"ramsar_id": 37, "name_en": "Lake Parishan and Dasht-e-Arjan", "name_fa": "دریاچه پریشان و دشت ارژن", "lat": 29.500000, "lon": 52.000000, "area_ha": 6200.0, "elev_min": 853, "elev_max": 2000, "montreux": False, "folder_hint": "parishan"},
    {"ramsar_id": 38, "name_en": "Lake Urmia [or Orumiyeh]", "name_fa": "دریاچه ارومیه", "lat": 37.500000, "lon": 45.500000, "area_ha": 483000.0, "elev_min": 1280, "elev_max": 1525, "montreux": False, "folder_hint": "urmia"},
    {"ramsar_id": 39, "name_en": "Neiriz Lakes & Kamjan Marshes", "name_fa": "دریاچه‌های نی‌ریز (بختگان و طشک) و باتلاق‌های کمجان", "lat": 29.666667, "lon": 53.500000, "area_ha": 108000.0, "elev_min": 1525, "elev_max": 1540, "montreux": True, "folder_hint": "neiriz"},
    {"ramsar_id": 40, "name_en": "Anzali Wetland", "name_fa": "تالاب انزلی", "lat": 37.440446, "lon": 49.411461, "area_ha": 19500.0, "elev_min": -27, "elev_max": -26, "montreux": True, "folder_hint": "anzali"},
    {"ramsar_id": 41, "name_en": "Shadegan Marshes & mudflats of Khor-al Amaya & Khor Musa", "name_fa": "تالاب شادگان و خورهای موسی و الامیه", "lat": 30.500000, "lon": 48.750000, "area_ha": 400000.0, "elev_min": 0, "elev_max": 15, "montreux": True, "folder_hint": "shadegan"},
    {"ramsar_id": 42, "name_en": "Hamun-e-Saberi & Hamun-e-Helmand", "name_fa": "هامون صابری و هامون هیرمند", "lat": 31.235753, "lon": 61.254341, "area_ha": 50000.0, "elev_min": 470, "elev_max": 475, "montreux": True, "folder_hint": "saberi"},
    {"ramsar_id": 43, "name_en": "Lake Kobi", "name_fa": "دریاچه کجی (قوری‌گل/کبی)", "lat": 36.950000, "lon": 45.500000, "area_ha": 1200.0, "elev_min": 1240, "elev_max": 1240, "montreux": False, "folder_hint": "kobi"},
    {"ramsar_id": 44, "name_en": "Hamun-e-Puzak, south end", "name_fa": "بخش جنوبی هامون پوزک", "lat": 31.333333, "lon": 61.750000, "area_ha": 10000.0, "elev_min": 490, "elev_max": 490, "montreux": True, "folder_hint": "puzak"},
    {"ramsar_id": 45, "name_en": "Shurgol, Yadegarlu & Dorgeh Sangi Lakes", "name_fa": "دریاچه‌های شورگل، یادگارلو و درگه سنگی", "lat": 37.000000, "lon": 45.500000, "area_ha": 2500.0, "elev_min": 1290, "elev_max": 1290, "montreux": True, "folder_hint": "shurgol"},
    {"ramsar_id": 46, "name_en": "Bujagh National Park", "name_fa": "پارک ملی بوجاق", "lat": 37.452096, "lon": 49.933978, "area_ha": 3433.0, "elev_min": -24, "elev_max": -23, "montreux": False, "folder_hint": "bujagh"},
    {"ramsar_id": 47, "name_en": "Amirkelayeh Lake", "name_fa": "تالاب امیرکلایه", "lat": 37.343668, "lon": 50.187540, "area_ha": 1131.6, "elev_min": -24, "elev_max": -23, "montreux": False, "folder_hint": "amirkelayeh"},
    {"ramsar_id": 48, "name_en": "Lake Gori", "name_fa": "تالاب قوری‌گل", "lat": 37.916667, "lon": 46.700000, "area_ha": 120.0, "elev_min": 1897, "elev_max": 1950, "montreux": False, "folder_hint": "gori"},
    {"ramsar_id": 49, "name_en": "Alagol, Ulmagol and Ajigol Lakes", "name_fa": "تالاب‌های آلاگل، آلماگل و آجی‌گل", "lat": 37.350000, "lon": 54.583333, "area_ha": 1400.0, "elev_min": 5, "elev_max": 5, "montreux": True, "folder_hint": "alagol"},
    {"ramsar_id": 50, "name_en": "Khuran Straits", "name_fa": "تنگه خوران (جنگل‌های حرا)", "lat": 26.750000, "lon": 55.666667, "area_ha": 100000.0, "elev_min": 0, "elev_max": 0, "montreux": False, "folder_hint": "khuran"},
    {"ramsar_id": 51, "name_en": "Deltas of Rud-e-Shur, Rud-e-Shirin and Rud-e-Minab", "name_fa": "دلتای رود شور، رود شیرین و رود میناب", "lat": 27.091552, "lon": 56.754657, "area_ha": 45000.0, "elev_min": 0, "elev_max": 0, "montreux": False, "folder_hint": "minab"},
    {"ramsar_id": 52, "name_en": "Deltas of Rud-e-Gaz and Rud-e-Hara", "name_fa": "دلتای رود گز و رود حرا", "lat": 26.666667, "lon": 57.333333, "area_ha": 15000.0, "elev_min": 0, "elev_max": 0, "montreux": False, "folder_hint": "gaz"},
    {"ramsar_id": 53, "name_en": "Gavkhouni Lake and marshes of the lower Zaindeh Rud", "name_fa": "تالاب گاوخونی و باتلاق‌های پایین‌دست زاینده‌رود", "lat": 32.333333, "lon": 52.783333, "area_ha": 43000.0, "elev_min": 1470, "elev_max": 1470, "montreux": False, "folder_hint": "gavkhouni"},
    {"ramsar_id": 1006, "name_en": "Govater Bay and Hur-e-Bahu", "name_fa": "خلیج گواتر و هور باهو", "lat": 25.166667, "lon": 61.500000, "area_ha": 75000.0, "elev_min": 0, "elev_max": 50, "montreux": False, "folder_hint": "govater"},
    {"ramsar_id": 1015, "name_en": "Sheedvar Island", "name_fa": "جزیره شیدور", "lat": 26.800000, "lon": 53.400000, "area_ha": 870.0, "elev_min": 0, "elev_max": 8, "montreux": False, "folder_hint": "sheedvar"},
    {"ramsar_id": 1109, "name_en": "Gomishan Lagoon", "name_fa": "تالاب گمیشان", "lat": 37.195808, "lon": 53.983491, "area_ha": 17700.0, "elev_min": -27, "elev_max": -27, "montreux": False, "folder_hint": "gomishan"},
    {"ramsar_id": 1308, "name_en": "Fereydoon Kenar, Ezbaran & Sorkh Ruds Ab-Bandans", "name_fa": "آب‌بندان‌های فریدون‌کنار، ازباران و سرخرود", "lat": 36.668283, "lon": 52.530905, "area_ha": 5427.0, "elev_min": -23, "elev_max": -23, "montreux": False, "folder_hint": "fereydoon"},
    {"ramsar_id": 1939, "name_en": "Choghakhor Wetland", "name_fa": "تالاب چغاخور", "lat": 31.916667, "lon": 50.900000, "area_ha": 1687.0, "elev_min": 2100, "elev_max": 2100, "montreux": False, "folder_hint": "choghakhor"},
    {"ramsar_id": 1940, "name_en": "Kanibarazan Wetland", "name_fa": "تالاب کانی‌برازان", "lat": 36.999191, "lon": 45.768822, "area_ha": 927.0, "elev_min": 1275, "elev_max": 1275, "montreux": False, "folder_hint": "kanibarazan"},
    {"ramsar_id": 2369, "name_en": "Zarivar", "name_fa": "تالاب زریوار", "lat": 35.542121, "lon": 46.125553, "area_ha": 2185.58, "elev_min": 1200, "elev_max": 2502, "montreux": False, "folder_hint": "zarivar"},
    {"ramsar_id": 2539, "name_en": "Barm Alvan", "name_fa": "تالاب برم الوان", "lat": 31.010192, "lon": 50.241123, "area_ha": 20.0, "elev_min": 1090, "elev_max": 1195, "montreux": False, "folder_hint": "alvan"},
    {"ramsar_id": 2558, "name_en": "Gandoman", "name_fa": "تالاب گندمان", "lat": 31.837169, "lon": 51.099501, "area_ha": 1070.0, "elev_min": 2207, "elev_max": 2229, "montreux": False, "folder_hint": "gandoman"},
    {"ramsar_id": 2601, "name_en": "Gahar Lake", "name_fa": "دریاچه گهر", "lat": 33.305433, "lon": 49.281028, "area_ha": 80.0, "elev_min": 2320, "elev_max": 2350, "montreux": False, "folder_hint": "gahar"}
]

def extract_nested_zips(input_dir: Path, work_dir: Path):
    """استخراج بازگشتی تمام فایل‌های زیپ تودرتو (شامل محدوده و نقشه ها.zip و features_param_idrvis.zip)"""
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith(".zip"):
                zip_path = Path(root) / f
                rel_parent = Path(root).relative_to(input_dir)
                target_sub = work_dir / rel_parent / zip_path.stem
                target_sub.mkdir(parents=True, exist_ok=True)
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(target_sub)
                except Exception as e:
                    print(f"[WARN] خطا در باز کردن {zip_path.name}: {e}")

    # مرحله دوم: باز کردن زیپ‌های داخلی استخراج‌شده (مانند features_param_idrvis.zip)
    for _ in range(2):
        for root, _, files in os.walk(work_dir):
            for f in files:
                if f.lower().endswith(".zip"):
                    zip_path = Path(root) / f
                    target_sub = Path(root) / f"{zip_path.stem}_extracted"
                    if not target_sub.exists():
                        target_sub.mkdir(parents=True, exist_ok=True)
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as zf:
                                zf.extractall(target_sub)
                        except Exception as e:
                            print(f"[WARN] خطا در باز کردن زیپ داخلی {zip_path.name}: {e}")

def create_fallback_circle_polygon(lat: float, lon: float, area_ha: float, num_points: int = 64) -> Polygon:
    """ایجاد پلیگون تقریبی استاندارد بر اساس مساحت رسمی (هکتار) و مختصات مرکز برای تالاب‌های فاقد شیپ‌فایل"""
    area_m2 = max(area_ha, 10.0) * 10000.0
    radius_m = math.sqrt(area_m2 / math.pi)
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(lat)))

    coords = []
    for i in range(num_points):
        angle = 2.0 * math.pi * i / num_points
        d_lat = radius_m * math.sin(angle) * lat_deg_per_m
        d_lon = radius_m * math.cos(angle) * lon_deg_per_m
        coords.append((round(lon + d_lon, 6), round(lat + d_lat, 6)))
    coords.append(coords[0])
    return Polygon(coords)

def match_shapefile_to_site(shp_path: Path, gdf: gpd.GeoDataFrame):
    """تطبیق هوشمند شیپ‌فایل با یکی از 28 سایت رامسر بر اساس نام پوشه و فاصله مکانی مرکز ثقل (Centroid)"""
    path_str = str(shp_path).lower()
    
    # محاسبه مرکز ثقل هندسه در سیستم WGS84
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    elif gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    geom_union = unary_union(gdf.geometry)
    centroid = geom_union.centroid
    c_lon, c_lat = centroid.x, centroid.y

    # ۱. بررسی فاصله مکانی مستقیم با مراکز ۲۸ سایت (دقیق‌ترین روش، مستقل از نام فایل)
    best_site = None
    min_dist = float("inf")
    for site in RAMSAR_SITES:
        dist = math.hypot(c_lat - site["lat"], c_lon - site["lon"])
        if dist < min_dist:
            min_dist = dist
            best_site = site

    # اگر فاصله مرکز پلیگون تا مرکز ثبت‌شده رامسر کمتر از 0.6 درجه (~60 کیلومتر) باشد، تطبیق قطعی است
    if best_site and min_dist < 0.6:
        return best_site, geom_union, gdf

    # ۲. پشتیبان: تطبیق از روی نام پوشه
    for site in RAMSAR_SITES:
        if site["folder_hint"] in path_str:
            return site, geom_union, gdf

    return None, geom_union, gdf

def process_all_sites():
    print("=" * 65)
    print("🚀 TerraScope Spatial Data Engine - Processing 28 Ramsar Wetlands")
    print("=" * 65)

    temp_dir = Path(tempfile.mkdtemp(prefix="terrascope_shp_"))
    matched_geoms = {}
    matched_sources = {}

    try:
        # ۱. کپی و استخراج هرگونه فایل زیپ یا شیپ‌فایل موجود در data/raw
        extract_nested_zips(RAW_DIR, temp_dir)

        # جستجوی تمام فایل‌های .shp در هر دو مسیر RAW_DIR و temp_dir
        shp_files = list(RAW_DIR.rglob("*.shp")) + list(temp_dir.rglob("*.shp"))
        print(f"[INFO] تعداد کل فایل‌های .shp کشف‌شده: {len(shp_files)}")

        for shp in shp_files:
            try:
                gdf = gpd.read_file(shp, engine="pyogrio")
                if gdf.empty:
                    continue
                site, geom, gdf_4326 = match_shapefile_to_site(shp, gdf)
                if site:
                    rid = site["ramsar_id"]
                    v_idris = int(gdf_4326["v_idris"].iloc[0]) if "v_idris" in gdf_4326.columns else None
                    matched_geoms[rid] = geom
                    matched_sources[rid] = {
                        "geometry_source": "Official RSIS Vector Shapefile",
                        "is_exact_boundary": True,
                        "v_idris": v_idris,
                        "source_file": shp.name
                    }
                    print(f"  ✅ [SHP MATCHED] IR{rid} -> {site['name_en']} (v_idris={v_idris})")
            except Exception as e:
                print(f"  ⚠️ [SHP ERROR] {shp.name}: {e}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ۲. ساخت GeoJSON تک‌تک ۲۸ تالاب + فایل جامع همه تالاب‌ها
    master_features = []
    summary_records = []

    for site in RAMSAR_SITES:
        rid = site["ramsar_id"]
        if rid in matched_geoms:
            geom = matched_geoms[rid]
            src_meta = matched_sources[rid]
        else:
            # ساخت مرز جایگزین استاندارد (Buffer Polygon) برای ۱۶ سایت فاقد شیپ‌فایل
            geom = create_fallback_circle_polygon(site["lat"], site["lon"], site["area_ha"])
            src_meta = {
                "geometry_source": "RSIS Centroid + Official Area Buffer (Pending Exact Polygon)",
                "is_exact_boundary": False,
                "v_idris": None,
                "source_file": "ramsar-sites-tabular.xlsx"
            }

        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        properties = {
            "ramsar_id": rid,
            "ris_code": f"IR{rid}",
            "name_en": site["name_en"],
            "name_fa": site["name_fa"],
            "lat": site["lat"],
            "lon": site["lon"],
            "area_ha": site["area_ha"],
            "elev_min_m": site["elev_min"],
            "elev_max_m": site["elev_max"],
            "montreux_listed": site["montreux"],
            "geometry_source": src_meta["geometry_source"],
            "is_exact_boundary": src_meta["is_exact_boundary"],
            "v_idris": src_meta["v_idris"],
            "bbox": [round(b, 6) for b in bounds],
            "ris_pdf": f"IR{rid}RIS.pdf"
        }

        feature = {
            "type": "Feature",
            "id": rid,
            "properties": properties,
            "geometry": mapping(geom)
        }
        master_features.append(feature)

        # ذخیره فایل GeoJSON اختصاصی هر تالاب
        single_fc = {"type": "FeatureCollection", "features": [feature]}
        out_file = GEOJSON_DIR / f"IR{rid}.geojson"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(single_fc, f, ensure_ascii=False)

        summary_records.append(properties)

    # ۳. ذخیره فایل جامع ۲۸ تالاب برای رندر سریع روی نقشه داشبورد
    master_fc = {
        "type": "FeatureCollection",
        "metadata": {
            "project": "TerraScope | Iran Ramsar Wetlands Observatory",
            "total_sites": len(master_features),
            "exact_vector_boundaries": sum(1 for r in summary_records if r["is_exact_boundary"]),
            "buffered_boundaries": sum(1 for r in summary_records if not r["is_exact_boundary"]),
            "crs": "EPSG:4326"
        },
        "features": master_features
    }

    master_geojson_path = GEOJSON_DIR / "iran_ramsar_28_sites.geojson"
    with open(master_geojson_path, "w", encoding="utf-8") as f:
        json.dump(master_fc, f, ensure_ascii=False, indent=2)

    catalog_json_path = PROCESSED_DIR / "wetlands_catalog.json"
    with open(catalog_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_records, f, ensure_ascii=False, indent=2)

    print("-" * 65)
    print(f"🎯 پردازش کامل شد!")
    print(f"   • کل تالاب‌های ثبت‌شده: {len(master_features)}")
    print(f"   • تالاب‌های دارای پلیگون دقیق (Shapefile): {master_fc['metadata']['exact_vector_boundaries']}")
    print(f"   • تالاب‌های دارای مرز محاسباتی (BBox/Buffer): {master_fc['metadata']['buffered_boundaries']}")
    print(f"   • خروجی جامع نقشه: {master_geojson_path}")
    print(f"   • کاتالوگ متادیتا: {catalog_json_path}")
    print("=" * 65)

if __name__ == "__main__":
    process_all_sites()
