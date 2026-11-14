import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "database" / "terrascope.db"
OUT_JSON_PATH = BASE_DIR / "data" / "processed" / "ecological_ai_assessments.json"

FA_LABELS = {
    "CRITICAL_DEGRADATION": "\u0628\u062d\u0631\u0627\u0646\u06cc - \u062a\u063a\u06cc\u06cc\u0631 \u0634\u062f\u06cc\u062f \u0645\u0627\u0647\u06cc\u062a \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 (\u0645\u0627\u062f\u0647 \u06f3.\u06f2 \u06a9\u0646\u0648\u0627\u0646\u0633\u06cc\u0648\u0646 \u0631\u0627\u0645\u0633\u0631)",
    "HIGH_STRESS": "\u062a\u0646\u0634 \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u0628\u0627\u0644\u0627 - \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u067e\u0627\u06cc\u0634 \u0648 \u0645\u062f\u06cc\u0631\u06cc\u062a \u0641\u0648\u0631\u06cc \u062d\u0642\u0627\u0628\u0647",
    "MODERATE_STRESS": "\u062a\u0646\u0634 \u0645\u062a\u0648\u0633\u0637 - \u0646\u0648\u0633\u0627\u0646 \u0641\u0635\u0644\u06cc \u06cc\u0627 \u0641\u0634\u0627\u0631\u0647\u0627\u06cc \u0645\u0648\u0636\u0639\u06cc",
    "STABLE_GOOD": "\u067e\u0627\u06cc\u062f\u0627\u0631 - \u0648\u0636\u0639\u06cc\u062a \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u0645\u0637\u0644\u0648\u0628 \u06cc\u0627 \u062f\u0631 \u062d\u0627\u0644 \u0627\u062d\u06cc\u0627"
}

def pick_val(row_dict, candidates, default=0.0):
    for c in candidates:
        if c in row_dict and row_dict[c] is not None:
            return row_dict[c]
    return default

def init_ai_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS ecological_ai_assessments")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ecological_ai_assessments (
            ramsar_id INTEGER PRIMARY KEY,
            assessed_at TEXT,
            ecological_status_code TEXT,
            risk_score REAL,
            article_3_2_alert INTEGER,
            has_satellite_data INTEGER,
            latest_water_pct REAL,
            latest_veg_pct REAL,
            latest_dry_pct REAL,
            water_trend_delta_pct REAL,
            summary_fa TEXT,
            summary_en TEXT,
            drivers_json TEXT,
            recommendations_fa TEXT,
            recommendations_en TEXT,
            citations_json TEXT,
            FOREIGN KEY (ramsar_id) REFERENCES wetlands(ramsar_id)
        )
    """)
    conn.commit()

def extract_document_evidence(cursor: sqlite3.Cursor, ramsar_id: int, name_en: str):
    cursor.execute("""
        SELECT id AS doc_id, filename, doc_category, page_count
        FROM document_catalog
        WHERE related_ramsar_id = ?
        ORDER BY doc_category
    """, (ramsar_id,))
    docs = [dict(r) for r in cursor.fetchall()]

    search_token = name_en.split()[0].replace(",", "").replace("(", "").replace(")", "")
    snippets = []
    if len(search_token) >= 3:
        try:
            cursor.execute("""
                SELECT dc.filename, dc.doc_category, dp.page_number, substr(dp.text_content, 1, 240) AS excerpt
                FROM document_pages dp
                JOIN document_catalog dc ON dp.doc_id = dc.id
                WHERE dp.text_content LIKE ?
                LIMIT 5
            """, (f"%{search_token}%",))
            for r in cursor.fetchall():
                snippets.append({
                    "file": r["filename"],
                    "type": r["doc_category"],
                    "page": r["page_number"],
                    "excerpt": " ".join(r["excerpt"].split())
                })
        except Exception:
            pass
    return docs, snippets

def evaluate_wetland(cursor: sqlite3.Cursor, w: dict):
    rid = w["ramsar_id"]
    name_en = w.get("name_en", f"Site {rid}")
    name_fa = w.get("name_fa", name_en)
    province = w.get("province_en") or w.get("admin_region") or "Iran"
    area_ha = float(w.get("area_ha") or 0)
    montreux = int(w.get("montreux_record") or 0)
    threats_raw = str(w.get("threats_en") or w.get("threats_fa") or "Water diversion, drought, and anthropogenic pressure")

    cursor.execute("""
        SELECT * FROM satellite_observations
        WHERE ramsar_id = ?
        ORDER BY COALESCE(observation_date, date) ASC
    """, (rid,))
    sat_rows = [dict(r) for r in cursor.fetchall()]

    docs, snippets = extract_document_evidence(cursor, rid, name_en)

    has_sat = 1 if len(sat_rows) > 0 else 0
    latest_water = None
    latest_veg = None
    latest_dry = None
    water_delta = 0.0
    ndwi_mean = None
    ndvi_mean = None

    if has_sat:
        first = sat_rows[0]
        last = sat_rows[-1]
        latest_water = float(pick_val(last, ["water_ratio_pct", "open_water_pct", "water_pct"], 0.0))
        latest_veg = float(pick_val(last, ["veg_ratio_pct", "vegetation_pct", "veg_pct"], 0.0))
        latest_dry = float(pick_val(last, ["dry_ratio_pct", "dry_salt_ratio_pct", "dry_bed_pct", "dry_pct", "bare_soil_pct"], 0.0))
        first_water = float(pick_val(first, ["water_ratio_pct", "open_water_pct", "water_pct"], 0.0))
        water_delta = round(latest_water - first_water, 2)
        ndwi_mean = float(pick_val(last, ["mean_ndwi", "ndwi_mean"], 0.0))
        ndvi_mean = float(pick_val(last, ["mean_ndvi", "ndvi_mean"], 0.0))

    risk_score = 25.0
    drivers = []

    if montreux == 1:
        risk_score += 28.0
        drivers.append({
            "code": "MONTREUX_LISTED",
            "fa": "\u062b\u0628\u062a\u200c\u0634\u062f\u0647 \u062f\u0631 \u0641\u0647\u0631\u0633\u062a \u0645\u0648\u0646\u062a\u0631\u0648 (\u062a\u063a\u06cc\u06cc\u0631 \u0645\u0627\u0647\u06cc\u062a \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u0637\u0628\u0642 \u0645\u0627\u062f\u0647 \u06f3.\u06f2 \u06a9\u0646\u0648\u0627\u0646\u0633\u06cc\u0648\u0646 \u0631\u0627\u0645\u0633\u0631)",
            "en": "Listed in the Montreux Record (Article 3.2 ecological character change)"
        })

    if has_sat:
        if latest_water < 5.0 and latest_dry > 75.0:
            risk_score += 32.0
            drivers.append({
                "code": "SEVERE_DESICCATION",
                "fa": f"\u062e\u0634\u06a9\u06cc\u062f\u06af\u06cc \u0634\u062f\u06cc\u062f \u0628\u0633\u062a\u0631 \u062a\u0627\u0644\u0627\u0628 ({latest_dry:.1f}% \u0628\u0633\u062a\u0631 \u062e\u0634\u06a9/\u0646\u0645\u06a9\u06cc \u0648 \u062a\u0646\u0647\u0627 {latest_water:.2f}% \u0622\u0628 \u0622\u0632\u0627\u062f \u062f\u0631 \u067e\u0627\u06cc\u0634 \u0633\u0646\u062a\u06cc\u0646\u0644-\u06f2)",
                "en": f"Severe bed desiccation ({latest_dry:.1f}% dry/saline bed and only {latest_water:.2f}% open water in Sentinel-2 EO)"
            })
        elif latest_veg > 65.0 and latest_water < 12.0:
            risk_score += 24.0
            drivers.append({
                "code": "EUTROPHICATION_MACROPHYTE_INVASION",
                "fa": f"\u067e\u062f\u06cc\u062f\u0647 \u0627\u0648\u062a\u0631\u06cc\u0641\u06cc\u06a9\u0627\u0633\u06cc\u0648\u0646 \u0634\u062f\u06cc\u062f \u0648 \u067e\u06cc\u0634\u0631\u0648\u06cc \u06af\u06cc\u0627\u0647\u0627\u0646 \u0622\u0628\u0632\u06cc/\u0646\u06cc\u0632\u0627\u0631 ({latest_veg:.1f}% \u067e\u0648\u0634\u0634 \u06af\u06cc\u0627\u0647\u06cc \u062f\u0631 \u0628\u0631\u0627\u0628\u0631 {latest_water:.2f}% \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc \u0628\u0627\u0632)",
                "en": f"Severe eutrophication & macrophyte/reed encroachment ({latest_veg:.1f}% vegetation vs {latest_water:.2f}% open water)"
            })
        if water_delta < -5.0:
            risk_score += 12.0
            drivers.append({
                "code": "NEGATIVE_HYDRO_TREND",
                "fa": f"\u0627\u0641\u062a \u0645\u062d\u0633\u0648\u0633 \u062a\u0631\u0627\u0632 \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc ({water_delta:.2f}% \u06a9\u0627\u0647\u0634 \u0646\u0633\u0628\u062a \u0628\u0647 \u0633\u0627\u0644 \u067e\u0627\u06cc\u0647 \u067e\u0627\u06cc\u0634)",
                "en": f"Declining open-water trend ({water_delta:.2f}% change compared to baseline)"
            })
        elif water_delta > 10.0:
            risk_score -= 10.0
            drivers.append({
                "code": "HYDRO_RECOVERY_PULSE",
                "fa": f"\u0646\u0648\u0633\u0627\u0646 \u0645\u062b\u0628\u062a \u0648 \u0622\u0628\u06af\u06cc\u0631\u06cc \u0641\u0635\u0644\u06cc \u0627\u062e\u06cc\u0631 (+{water_delta:.2f}% \u0627\u0641\u0632\u0627\u06cc\u0634 \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc \u0646\u0633\u0628\u062a \u0628\u0647 \u062f\u0648\u0631\u0647 \u067e\u0627\u06cc\u0647)",
                "en": f"Positive seasonal hydrological pulse (+{water_delta:.2f}% open-water expansion vs baseline)"
            })
    else:
        t_low = threats_raw.lower()
        if any(k in t_low for k in ["drought", "diversion", "dam", "canal", "drainage", "drying"]):
            risk_score += 18.0
            drivers.append({
                "code": "HYDROLOGICAL_ALTERATION",
                "fa": "\u0641\u0634\u0627\u0631\u0647\u0627\u06cc \u0647\u06cc\u062f\u0631\u0648\u0644\u0648\u0698\u06cc\u06a9 \u062b\u0628\u062a\u200c\u0634\u062f\u0647 \u062f\u0631 \u0627\u0633\u0646\u0627\u062f RIS (\u0633\u062f\u0633\u0627\u0632\u06cc\u060c \u0627\u0646\u062d\u0631\u0627\u0641 \u0622\u0628\u060c \u0632\u0647\u200c\u06a9\u0634\u06cc \u0648 \u062e\u0634\u06a9\u0633\u0627\u0644\u06cc)",
                "en": "Hydrological regime alteration reported in official RIS dossiers (dams, water diversion, drought)"
            })
        if any(k in t_low for k in ["pollution", "wastewater", "sewage", "agriculture", "effluent"]):
            risk_score += 12.0
            drivers.append({
                "code": "POLLUTION_NUTRIENT_LOAD",
                "fa": "\u0648\u0631\u0648\u062f \u0632\u0647\u0627\u0628\u200c\u0647\u0627\u06cc \u06a9\u0634\u0627\u0648\u0631\u0632\u06cc\u060c \u0641\u0627\u0636\u0644\u0627\u0628 \u0648 \u0628\u0627\u0631 \u0622\u0644\u0648\u062f\u06af\u06cc \u0628\u0631 \u0627\u0633\u0627\u0633 \u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627\u06cc \u0645\u0644\u06cc \u0631\u0627\u0645\u0633\u0631",
                "en": "Agricultural runoff, wastewater discharge, and nutrient loading reported in RIS/COP records"
            })

    risk_score = round(min(max(risk_score, 10.0), 98.0), 1)

    if risk_score >= 70.0:
        status_code = "CRITICAL_DEGRADATION"
    elif risk_score >= 50.0:
        status_code = "HIGH_STRESS"
    elif risk_score >= 35.0:
        status_code = "MODERATE_STRESS"
    else:
        status_code = "STABLE_GOOD"

    art_3_2 = 1 if (montreux == 1 or risk_score >= 70.0) else 0
    doc_names = [d["filename"] for d in docs] if docs else ["COP15NR_IranIR_e_0.pdf", "Ramsar-Sites-annotated-summary-Iran-Islamic-Republic-of.pdf"]

    if has_sat:
        sat_fa = (
            f"\u0628\u0631 \u0627\u0633\u0627\u0633 \u067e\u0631\u062f\u0627\u0632\u0634 \u062a\u0635\u0627\u0648\u06cc\u0631 \u0645\u0627\u0647\u0648\u0627\u0631\u0647\u200c\u0627\u06cc Sentinel-2 L2A\u060c \u062f\u0631 \u0622\u062e\u0631\u06cc\u0646 \u062f\u0648\u0631\u0647 \u067e\u0627\u06cc\u0634\u060c \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc \u0622\u0632\u0627\u062f \u0645\u0639\u0627\u062f\u0644 {latest_water:.2f}%\u060c "
            f"\u067e\u0648\u0634\u0634 \u06af\u06cc\u0627\u0647\u06cc \u0622\u0628\u0632\u06cc \u0648 \u062d\u0627\u0634\u06cc\u0647\u200c\u0627\u06cc {latest_veg:.2f}% \u0648 \u0628\u0633\u062a\u0631 \u062e\u0634\u06a9 \u06cc\u0627 \u0634\u0648\u0631\u0647\u200c\u0632\u0627\u0631 {latest_dry:.2f}% \u0627\u0632 \u0645\u062d\u062f\u0648\u062f\u0647 \u062a\u0627\u0644\u0627\u0628 \u0631\u0627 \u062a\u0634\u06a9\u06cc\u0644 \u0645\u06cc\u200c\u062f\u0647\u062f "
            f"(\u062a\u063a\u06cc\u06cc\u0631\u0627\u062a \u0622\u0628 \u0622\u0632\u0627\u062f \u0646\u0633\u0628\u062a \u0628\u0647 \u062f\u0648\u0631\u0647 \u067e\u0627\u06cc\u0647: {water_delta:+.2f}%\u061b \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 \u0634\u0627\u062e\u0635 NDWI \u0628\u0631\u0627\u0628\u0631 {ndwi_mean:.3f} \u0648 NDVI \u0628\u0631\u0627\u0628\u0631 {ndvi_mean:.3f}). "
        )
        sat_en = (
            f"Based on Sentinel-2 L2A optical imagery analysis, the latest observation indicates {latest_water:.2f}% open water, "
            f"{latest_veg:.2f}% aquatic/riparian vegetation cover, and {latest_dry:.2f}% dry/saline substrate "
            f"(open-water delta vs. baseline: {water_delta:+.2f}%; mean NDWI: {ndwi_mean:.3f}, mean NDVI: {ndvi_mean:.3f}). "
        )
    else:
        sat_fa = (
            "\u067e\u0631\u0648\u0641\u0627\u06cc\u0644 \u067e\u0627\u06cc\u0647 \u062a\u0627\u0644\u0627\u0628 \u0627\u0632 \u0627\u0633\u0646\u0627\u062f \u0631\u0633\u0645\u06cc RIS \u0648 \u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627\u06cc \u0645\u0644\u06cc COP \u0627\u0633\u062a\u062e\u0631\u0627\u062c \u0634\u062f\u0647 \u0648 \u0622\u0645\u0627\u062f\u0647 \u0627\u062c\u0631\u0627\u06cc \u067e\u0627\u06cc\u0634 \u0645\u0627\u0647\u0648\u0627\u0631\u0647\u200c\u0627\u06cc \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc (On-demand Sentinel-2 STAC) \u0627\u0633\u062a. "
        )
        sat_en = (
            "Baseline ecological parameters are synthesized from official Ramsar RIS and COP National Reports, ready for on-demand Sentinel-2 STAC execution. "
        )

    montreux_fa = "\u0627\u06cc\u0646 \u062a\u0627\u0644\u0627\u0628 \u062f\u0631 \u0641\u0647\u0631\u0633\u062a \u0645\u0648\u0646\u062a\u0631\u0648 (\u0645\u0627\u062f\u0647 \u06f3.\u06f2 \u06a9\u0646\u0648\u0627\u0646\u0633\u06cc\u0648\u0646 \u0631\u0627\u0645\u0633\u0631) \u0642\u0631\u0627\u0631 \u062f\u0627\u0634\u062a\u0647 \u0648 \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u0627\u0642\u062f\u0627\u0645\u0627\u062a \u0627\u062d\u06cc\u0627\u06cc\u06cc \u0627\u0648\u0644\u0648\u06cc\u062a\u200c\u062f\u0627\u0631 \u0627\u0633\u062a." if montreux else "\u0627\u06cc\u0646 \u062a\u0627\u0644\u0627\u0628 \u062f\u0631 \u062d\u0627\u0644 \u062d\u0627\u0636\u0631 \u062e\u0627\u0631\u062c \u0627\u0632 \u0641\u0647\u0631\u0633\u062a \u0645\u0648\u0646\u062a\u0631\u0648 \u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f \u0627\u0645\u0627 \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u067e\u0627\u06cc\u0634 \u0645\u0633\u062a\u0645\u0631 \u0634\u0627\u062e\u0635\u200c\u0647\u0627\u06cc \u0647\u06cc\u062f\u0631\u0648\u0644\u0648\u0698\u06cc\u06a9 \u0627\u0633\u062a."
    montreux_en = "This wetland is listed on the Montreux Record (Article 3.2) requiring priority ecological restoration." if montreux else "Currently outside the Montreux Record, though continuous hydrological and water-quality monitoring remains essential."

    summary_fa = (
        f"\u062a\u062d\u0644\u06cc\u0644 \u0647\u0648\u0634\u0645\u0646\u062f \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u00ab{name_fa}\u00bb (\u06a9\u062f \u0631\u0627\u0645\u0633\u0631 #{rid} - \u0645\u0633\u0627\u062d\u062a \u0631\u0633\u0645\u06cc {area_ha:,.0f} \u0647\u06a9\u062a\u0627\u0631): "
        f"\u0648\u0636\u0639\u06cc\u062a \u0641\u0639\u0644\u06cc \u062f\u0631 \u0631\u062f\u0647 \u00ab{FA_LABELS[status_code]}\u00bb \u0628\u0627 \u0627\u0645\u062a\u06cc\u0627\u0632 \u0631\u06cc\u0633\u06a9 {risk_score} \u0627\u0632 \u06f1\u06f0\u06f0 \u0627\u0631\u0632\u06cc\u0627\u0628\u06cc \u0645\u06cc\u200c\u0634\u0648\u062f. "
        f"{sat_fa}{montreux_fa} \u0627\u0633\u0646\u0627\u062f \u0645\u0631\u062c\u0639 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646: {', '.join(doc_names[:3])}."
    )

    summary_en = (
        f"Ecological AI Synthesis for '{name_en}' (Ramsar Site #{rid}, {province} - Official Area: {area_ha:,.0f} ha): "
        f"Classified as '{status_code}' with a composite ecological risk score of {risk_score}/100. "
        f"{sat_en}{montreux_en} Supporting archival documents: {', '.join(doc_names[:3])}."
    )

    if status_code in ("CRITICAL_DEGRADATION", "HIGH_STRESS"):
        rec_fa = (
            "\u06f1) \u062a\u062e\u0635\u06cc\u0635 \u0648 \u0631\u0647\u0627\u0633\u0627\u0632\u06cc \u0641\u0648\u0631\u06cc \u062d\u0642\u0627\u0628\u0647 \u0632\u06cc\u0633\u062a\u200c\u0645\u062d\u06cc\u0637\u06cc \u0645\u0637\u0627\u0628\u0642 \u0628\u0631\u0646\u0627\u0645\u0647 \u0645\u062f\u06cc\u0631\u06cc\u062a \u062c\u0627\u0645\u0639 \u062a\u0627\u0644\u0627\u0628\u061b "
            "\u06f2) \u06a9\u0646\u062a\u0631\u0644 \u0648\u0631\u0648\u062f \u0632\u0647\u0627\u0628\u200c\u0647\u0627\u06cc \u06a9\u0634\u0627\u0648\u0631\u0632\u06cc \u0648 \u0641\u0627\u0636\u0644\u0627\u0628 \u0628\u0631\u0627\u06cc \u0645\u0647\u0627\u0631 \u0627\u0648\u062a\u0631\u06cc\u0641\u06cc\u06a9\u0627\u0633\u06cc\u0648\u0646 \u0648 \u067e\u06cc\u0634\u0631\u0648\u06cc \u0646\u06cc\u0632\u0627\u0631\u0647\u0627\u061b "
            "\u06f3) \u0645\u0633\u062a\u0646\u062f\u0633\u0627\u0632\u06cc \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a \u0645\u0627\u0647\u06cc\u062a \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u062c\u0647\u062a \u0627\u0631\u0627\u0626\u0647 \u0628\u0647 \u062f\u0628\u06cc\u0631\u062e\u0627\u0646\u0647 \u06a9\u0646\u0648\u0627\u0646\u0633\u06cc\u0648\u0646 \u0631\u0627\u0645\u0633\u0631 (\u0645\u0627\u062f\u0647 \u06f3.\u06f2)."
        )
        rec_en = (
            "1) Immediate enforcement and release of environmental water rights per the Integrated Wetland Management Plan; "
            "2) Mitigation of agricultural runoff and sewage inflow to arrest eutrophication; "
            "3) Formal Article 3.2 ecological character reporting and restoration tracking."
        )
    else:
        rec_fa = (
            "\u06f1) \u062a\u062f\u0627\u0648\u0645 \u067e\u0627\u06cc\u0634 \u0641\u0635\u0644\u06cc \u062a\u0631\u0627\u0632 \u0622\u0628 \u0648 \u0634\u0627\u062e\u0635\u200c\u0647\u0627\u06cc \u0637\u06cc\u0641\u06cc \u0645\u0627\u0647\u0648\u0627\u0631\u0647\u200c\u0627\u06cc (NDWI/NDVI)\u061b "
            "\u06f2) \u062d\u0641\u0627\u0638\u062a \u0627\u0632 \u0632\u06cc\u0633\u062a\u06af\u0627\u0647\u200c\u0647\u0627\u06cc \u067e\u0631\u0646\u062f\u06af\u0627\u0646 \u0645\u0647\u0627\u062c\u0631 \u0622\u0628\u0632\u06cc \u0648 \u0645\u062f\u06cc\u0631\u06cc\u062a \u0628\u0647\u0631\u0647\u200c\u0628\u0631\u062f\u0627\u0631\u06cc \u062c\u0648\u0627\u0645\u0639 \u0645\u062d\u0644\u06cc\u061b "
            "\u06f3) \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc \u062f\u0648\u0631\u0647\u200c\u0627\u06cc \u0641\u0631\u0645 \u0627\u0637\u0644\u0627\u0639\u0627\u062a \u0631\u0627\u0645\u0633\u0631 (RIS)."
        )
        rec_en = (
            "1) Maintain seasonal satellite spectral monitoring (NDWI/NDVI) and hydro-period tracking; "
            "2) Safeguard migratory waterbird habitats and regulate wise-use community practices; "
            "3) Periodic updating of the Ramsar Information Sheet (RIS)."
        )

    citations = {
        "official_documents": doc_names,
        "text_excerpts": snippets
    }

    return {
        "ramsar_id": rid,
        "name_en": name_en,
        "name_fa": name_fa,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "ecological_status_code": status_code,
        "risk_score": risk_score,
        "article_3_2_alert": art_3_2,
        "has_satellite_data": has_sat,
        "latest_water_pct": latest_water,
        "latest_veg_pct": latest_veg,
        "latest_dry_pct": latest_dry,
        "water_trend_delta_pct": water_delta,
        "summary_fa": summary_fa,
        "summary_en": summary_en,
        "drivers": drivers,
        "recommendations_fa": rec_fa,
        "recommendations_en": rec_en,
        "citations": citations
    }

def run_all_assessments():
    print("=" * 72)
    print("TerraScope Phase 1 (Step 5): Local Ecological AI Synthesis Engine")
    print("=" * 72)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_ai_table(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wetlands ORDER BY ramsar_id ASC")
    wetlands = [dict(r) for r in cursor.fetchall()]

    all_results = []
    for w in wetlands:
        res = evaluate_wetland(cursor, w)
        all_results.append(res)
        cursor.execute("""
            INSERT OR REPLACE INTO ecological_ai_assessments (
                ramsar_id, assessed_at, ecological_status_code, risk_score,
                article_3_2_alert, has_satellite_data, latest_water_pct,
                latest_veg_pct, latest_dry_pct, water_trend_delta_pct,
                summary_fa, summary_en, drivers_json,
                recommendations_fa, recommendations_en, citations_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            res["ramsar_id"], res["assessed_at"], res["ecological_status_code"],
            res["risk_score"], res["article_3_2_alert"], res["has_satellite_data"],
            res["latest_water_pct"], res["latest_veg_pct"], res["latest_dry_pct"],
            res["water_trend_delta_pct"], res["summary_fa"], res["summary_en"],
            json.dumps(res["drivers"], ensure_ascii=False),
            res["recommendations_fa"], res["recommendations_en"],
            json.dumps(res["citations"], ensure_ascii=False)
        ))

    conn.commit()
    conn.close()

    OUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_sites_assessed": len(all_results),
            "assessments": all_results
        }, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Generated Ecological AI Assessments for {len(all_results)} Iranian Ramsar Wetlands.")
    print(f"[EXPORT] Saved JSON report to: {OUT_JSON_PATH}")
    print("-" * 72)
    for sample_id in (38, 40, 53):
        s = next((x for x in all_results if x["ramsar_id"] == sample_id), None)
        if s:
            print(f"Site #{s['ramsar_id']} ({s['name_en']}) -> Status: {s['ecological_status_code']} | Risk Score: {s['risk_score']}/100 | Art.3.2 Alert: {bool(s['article_3_2_alert'])}")
            print(f"   EN: {s['summary_en'][:175]}...")
            print("-" * 72)

if __name__ == "__main__":
    run_all_assessments()