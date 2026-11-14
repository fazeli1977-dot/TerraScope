import os
import re
import json
import shutil
import zipfile
from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(r"C:\Projects\TerraScope")
RAW_DIR = BASE_DIR / "data" / "raw"
DOCS_DIR = BASE_DIR / "data" / "documents"
MAPS_DIR = BASE_DIR / "data" / "maps"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
(DOCS_DIR / "ris").mkdir(parents=True, exist_ok=True)
(DOCS_DIR / "national_reports").mkdir(parents=True, exist_ok=True)
MAPS_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_PATH = PROCESSED_DIR / "wetlands_catalog.json"

def extract_all_archives():
    """استخراج فایل‌های PDF، JPG، PNG و XLSX از تمام آرشیوهای زیپ موجود در data/raw"""
    temp_extract = BASE_DIR / "data" / "_temp_docs"
    temp_extract.mkdir(parents=True, exist_ok=True)

    for zf_path in RAW_DIR.glob("*.zip"):
        try:
            with zipfile.ZipFile(zf_path, 'r') as zf:
                zf.extractall(temp_extract / zf_path.stem)
            print(f"📦 آرشیو استخراج شد: {zf_path.name}")
        except Exception as e:
            print(f"⚠️ خطا در باز کردن {zf_path.name}: {e}")

    return temp_extract

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_ris_summary(pdf_path: Path) -> dict:
    """استخراج هوشمند خلاصه اکولوژیک، تهدیدها و ویژگی‌های هیدرولوژیکی از فایل PDF رسمی RIS"""
    info = {
        "page_count": 0,
        "ecological_features": "",
        "threats_factors": "",
        "hydrological_values": "",
        "raw_excerpt": ""
    }
    try:
        reader = PdfReader(str(pdf_path))
        info["page_count"] = len(reader.pages)
        full_text = []
        for idx, page in enumerate(reader.pages[:12]):  # خواندن ۱۲ صفحه اول برای سرعت بالا
            txt = page.extract_text() or ""
            full_text.append(txt)
        joined = clean_text(" ".join(full_text))
        info["raw_excerpt"] = joined[:2500]

        # جستجوی کلیدواژه‌های استاندارد فرم RIS رامسر
        eco_match = re.search(r'(?: Ecological character|general overview| ecological features|Justification|Criteria)(.*?)(?:Hydrological|Physical|Social|Adverse|Threats|$)', joined, re.IGNORECASE)
        if eco_match:
            info["ecological_features"] = eco_match.group(1).strip()[:800]

        threat_match = re.search(r'(?:Adverse factors|Threats|factors .*? adversely affecting)(.*?)(?:Conservation|Management|Jurisdiction|Bibliographical|$)', joined, re.IGNORECASE)
        if threat_match:
            info["threats_factors"] = threat_match.group(1).strip()[:800]

        hydro_match = re.search(r'(?:Hydrological values|Physical features|hydrology)(.*?)(?:Ecological|Noteworthy|Social|Land tenure|$)', joined, re.IGNORECASE)
        if hydro_match:
            info["hydrological_values"] = hydro_match.group(1).strip()[:800]

    except Exception as e:
        print(f"  ⚠️ خطا در خواندن PDF ({pdf_path.name}): {e}")

    return info

def build_document_repository():
    print("=" * 65)
    print("📚 TerraScope Document & Local AI Knowledge Base Indexer")
    print("=" * 65)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    temp_extract = extract_all_archives()

    # جمع‌آوری تمام فایل‌های استخراج‌شده + فایل‌های موجود در raw
    all_files = list(temp_extract.rglob("*.*")) + list(RAW_DIR.rglob("*.*"))

    ris_files_map = {}      # ramsar_id -> filename
    map_files_map = {}      # ramsar_id -> list of filenames
    national_reports = []

    for fpath in all_files:
        if not fpath.is_file():
            continue
        fname = fpath.name
        lower_name = fname.lower()

        # ۱. شناسایی فایل‌های شناسنامه RIS (مثلاً IR40RIS_2304_en.pdf یا IR36RIS.pdf)
        ris_match = re.match(r'^ir(\d+)ris.*\.pdf$', lower_name)
        if ris_match:
            rid = int(ris_match.group(1))
            std_name = f"IR{rid}RIS.pdf"
            dest = DOCS_DIR / "ris" / std_name
            shutil.copy2(fpath, dest)
            ris_files_map[rid] = std_name
            continue

        # ۲. شناسایی نقشه‌های رسمی تالاب‌ها (مثلاً IR40_map180515.jpg یا IR36map.pdf)
        map_match = re.match(r'^ir(\d+)_?map.*\.(pdf|jpg|jpeg|png)$', lower_name)
        if map_match:
            rid = int(map_match.group(1))
            dest = MAPS_DIR / fname
            shutil.copy2(fpath, dest)
            map_files_map.setdefault(rid, [])
            if fname not in map_files_map[rid]:
                map_files_map[rid].append(fname)
            continue

        # ۳. شناسایی گزارش‌های ملی کنوانسیون رامسر (COP7 تا COP15 و طرح‌های مدیریت)
        if lower_name.endswith(".pdf") and any(k in lower_name for k in ["cop", "managementplan", "montreux", "annotated", "national_wetland", "ram"]):
            dest = DOCS_DIR / "national_reports" / fname
            shutil.copy2(fpath, dest)
            if fname not in national_reports:
                national_reports.append(fname)

    # پاکسازی پوشه موقت
    shutil.rmtree(temp_extract, ignore_errors=True)

    # ۴. بروزرسانی کاتالوگ ۲۸ تالاب و ساخت بانک دانش هوش مصنوعی محلی
    ai_knowledge_base = {}

    for site in catalog:
        rid = site["ramsar_id"]
        has_ris = rid in ris_files_map
        site["ris_pdf_available"] = has_ris
        site["ris_pdf_url"] = f"/data/documents/ris/IR{rid}RIS.pdf" if has_ris else None
        site["official_maps"] = [f"/data/maps/{m}" for m in map_files_map.get(rid, [])]

        # استخراج دانش از PDF در صورت وجود، یا ساخت پروفایل استاندارد علمی
        ris_path = DOCS_DIR / "ris" / f"IR{rid}RIS.pdf"
        pdf_knowledge = extract_ris_summary(ris_path) if ris_path.exists() else {
            "page_count": 0, "ecological_features": "", "threats_factors": "", "hydrological_values": "", "raw_excerpt": ""
        }

        ai_knowledge_base[str(rid)] = {
            "ramsar_id": rid,
            "ris_code": f"IR{rid}",
            "name_fa": site["name_fa"],
            "name_en": site["name_en"],
            "area_ha": site["area_ha"],
            "montreux_listed": site["montreux_listed"],
            "elev_range_m": [site["elev_min_m"], site["elev_max_m"]],
            "is_exact_boundary": site["is_exact_boundary"],
            "ris_document_pages": pdf_knowledge["page_count"],
            "ecological_features": pdf_knowledge["ecological_features"],
            "threats_factors": pdf_knowledge["threats_factors"],
            "hydrological_values": pdf_knowledge["hydrological_values"],
            "raw_excerpt": pdf_knowledge["raw_excerpt"],
            "last_updated": "2026-11-14"
        }

    # ذخیره کاتالوگ بروزرسانی‌شده
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    # ذخیره بانک دانش هوش مصنوعی محلی
    kb_path = PROCESSED_DIR / "wetlands_knowledge_base.json"
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump({
            "national_reports": sorted(national_reports),
            "sites_knowledge": ai_knowledge_base
        }, f, ensure_ascii=False, indent=2)

    print("-" * 65)
    print(f"✅ تعداد شناسنامه‌های RIS استخراج‌شده: {len(ris_files_map)} از 28 تالاب")
    print(f"✅ تعداد تالاب‌های دارای نقشه رسمی (PDF/JPG): {len(map_files_map)}")
    print(f"✅ تعداد گزارش‌های ملی COP و طرح‌های مدیریتی: {len(national_reports)}")
    print(f"✅ بانک دانش هوش مصنوعی محلی ساخته شد: {kb_path}")
    print("=" * 65)

if __name__ == "__main__":
    build_document_repository()
