import os
import zipfile
import geopandas as gpd
import pandas as pd
import shutil
import tempfile
from pathlib import Path

# نگاشت دقیق نام پوشه‌های داخل آرشیو رامسر به شناسه رسمی کنوانسیون (Ramsar ID)
RAMSAR_ID_MAP = {
    "amirkelayeh lake": "47",
    "Anzali Wetland": "40",
    "Bujagh National Park": "46",
    "Deltas of Rud-e-Shur, Rud-e-Shirin and Rud-e-Minab": "51",
    "Fereydoon Kenar, Ezbaran & Sorkh Ruds Ab-Bandans": "1308",
    "Gahar Lake": "2601",
    "Gandoman": "2558",
    "Gomishan Lagoon": "1109",
    "Hamun-e-Saberi & Hamun-e-Helmand": "42",
    "Kanibarazan Wetland": "1940",
    "Miankaleh Peninsula, Gorgan Bay and Lapoo-Zaghmarz Ab-bandan": "36",
    "Zarivar": "2369"
}

BASE_DIR = Path(__file__).resolve().parent.parent

# پوشش تمام مسیرهای احتمالی فرانت‌اند در پروژه شما
OUTPUT_DIRS = [
    BASE_DIR / "frontend" / "public" / "data" / "boundaries",
    BASE_DIR / "public" / "data" / "boundaries"
]

def find_maps_source():
    """پیدا کردن پوشه یا فایل زیپ نقشه‌ها در مسیرهای مختلف پروژه یا پوشه Downloads"""
    candidates = [
        BASE_DIR / "محدوده و نقشه ها",
        BASE_DIR / "data" / "محدوده و نقشه ها",
        BASE_DIR / "محدوده و نقشه ها.zip",
        BASE_DIR / "data" / "محدوده و نقشه ها.zip",
        Path.home() / "Downloads" / "محدوده و نقشه ها.zip",
        Path.home() / "Desktop" / "محدوده و نقشه ها.zip"
    ]
    for c in candidates:
        if c.exists():
            return c
    # جستجوی خودکار در کل پروژه برای هر فایلی که شامل نام نقشه باشد
    for p in BASE_DIR.rglob("*نقشه*"):
        if p.is_dir() or p.suffix.lower() == '.zip':
            return p
    return None

def process_boundaries():
    print("🚀 Starting Automated Ramsar Boundary Shapefile -> GeoJSON Pipeline...")
    
    for out_dir in OUTPUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)

    source = find_maps_source()
    if not source:
        print("❌ خطا: پوشه یا فایل 'محدوده و نقشه ها.zip' پیدا نشد!")
        print(f"لطفاً فایل 'محدوده و نقشه ها.zip' را در مسیر {BASE_DIR} کپی کنید و دوباره دستور را اجرا نمایید.")
        return

    print(f"📂 Source found: {source}")
    temp_root = Path(tempfile.mkdtemp())
    all_gdfs = []
    success_count = 0

    try:
        # اگر منبع یک فایل زیپ کلی است، ابتدا آن را در پوشه موقت باز می‌کنیم
        if source.is_file() and source.suffix.lower() == '.zip':
            print("📦 Extracting master archive...")
            master_extract = temp_root / "master"
            with zipfile.ZipFile(source, 'r') as zf:
                zf.extractall(master_extract)
            search_root = master_extract
        else:
            search_root = source

        # پیمایش روی ۱۲ تالاب دارای شیپ‌فایل
        for folder_name, ramsar_id in RAMSAR_ID_MAP.items():
            # پیدا کردن پوشه مربوط به تالاب (بدون حساسیت به حروف بزرگ و کوچک)
            target_folder = None
            for root, dirs, files in os.walk(search_root):
                for d in dirs:
                    if d.strip().lower() == folder_name.lower():
                        target_folder = Path(root) / d
                        break
                if target_folder:
                    break

            if not target_folder:
                print(f"⚠️ Folder not found for: {folder_name} (ID: {ramsar_id})")
                continue

            # پیدا کردن فایل زیپ شیپ‌فایل (features_param_idrvis.zip)
            shp_zip = None
            for f in target_folder.iterdir():
                if f.suffix.lower() == '.zip' and 'features_param_idrvis' in f.name.lower():
                    shp_zip = f
                    break

            if not shp_zip:
                print(f"⚠️ No shapefile zip inside: {folder_name}")
                continue

            # استخراج شیپ‌فایل
            shp_extract_dir = temp_root / f"shp_{ramsar_id}"
            with zipfile.ZipFile(shp_zip, 'r') as zf:
                zf.extractall(shp_extract_dir)

            # پیدا کردن فایل .shp
            shp_files = list(shp_extract_dir.rglob("*.shp"))
            if not shp_files:
                print(f"⚠️ No .shp file found inside zip for {folder_name}")
                continue

            shp_path = shp_files[0]
            try:
                gdf = gpd.read_file(shp_path)
                # اطمینان از سیستم مختصات استاندارد وب (WGS84 / EPSG:4326)
                if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(epsg=4326)
                elif gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)

                # افزودن متادیتای استاندارد رامسر به جدول توصیفی GeoJSON
                gdf["ramsar_id"] = int(ramsar_id)
                gdf["site_name"] = folder_name

                # ذخیره در پوشه‌های فرانت‌اند با نام {ramsar_id}.geojson و IR{ramsar_id}.geojson
                for out_dir in OUTPUT_DIRS:
                    out_file_1 = out_dir / f"{ramsar_id}.geojson"
                    out_file_2 = out_dir / f"IR{ramsar_id}.geojson"
                    gdf.to_file(out_file_1, driver="GeoJSON")
                    gdf.to_file(out_file_2, driver="GeoJSON")

                all_gdfs.append(gdf)
                print(f"✅ Converted: {folder_name} -> {ramsar_id}.geojson (EPSG:4326)")
                success_count += 1

            except Exception as e:
                print(f"❌ Error converting {folder_name}: {e}")

        # ساخت یک فایل GeoJSON جامع شامل مرز تمام تالاب‌ها برای لود یکپارچه روی نقشه
        if all_gdfs:
            combined_gdf = gpd.GeoDataFrame(pd.concat(all_gdfs, ignore_index=True), crs="EPSG:4326")
            for out_dir in OUTPUT_DIRS:
                combined_path = out_dir / "all_boundaries.geojson"
                combined_gdf.to_file(combined_path, driver="GeoJSON")
            print(f"🌍 Master file created: all_boundaries.geojson ({len(all_gdfs)} sites)")

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(f"\n🎉 Done! {success_count} wetland boundaries exported successfully.")

if __name__ == "__main__":
    process_boundaries()
