# -*- coding: utf-8 -*-
import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "data" / "database" / "terrascope.db"
EXPORT_PATH = BASE_DIR / "data" / "processed" / "ai_ecological_assessments.json"

FA = {
    "CRITICAL": "\u0628\u062d\u0631\u0627\u0646\u06cc / \u062a\u063a\u06cc\u06cc\u0631 \u0645\u0627\u0647\u06cc\u062a \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 (\u0645\u0627\u062f\u0647 \u06f3.\u06f2)",
    "STRESSED": "\u062a\u0646\u0634 \u0622\u0628\u06cc \u0648 \u0627\u06a9\u0648\u0644\u0648\u0698\u06cc\u06a9 \u0634\u062f\u06cc\u062f",
    "MODERATE": "\u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u067e\u0627\u06cc\u0634 \u0648 \u062d\u0641\u0638 \u062d\u0642\u0627\u0628\u0647",
    "STABLE": "\u067e\u0627\u06cc\u062f\u0627\u0631\u06cc \u0646\u0633\u0628\u06cc \u0632\u06cc\u0633\u062a\u200c\u0628\u0648\u0645",
    "MONTREUX_YES": "\u062f\u0627\u0631\u0627\u06cc \u0648\u0636\u0639\u06cc\u062a/\u0633\u0627\u0628\u0642\u0647 \u0641\u0647\u0631\u0633\u062a \u0645\u0648\u0646\u062a\u0631\u0648 (\u0645\u0627\u062f\u0647 \u06f3.\u06f2)",
    "MONTREUX_NO": "\u062e\u0627\u0631\u062c \u0627\u0632 \u0641\u0647\u0631\u0633\u062a \u0645\u0648\u0646\u062a\u0631\u0648",
    "REC_DROUGHT": "\u062a\u0627\u0645\u06cc\u0646 \u0641\u0648\u0631\u06cc \u062d\u0642\u0627\u0628\u0647 \u0632\u06cc\u0633\u062a\u200c\u0645\u062d\u06cc\u0637\u06cc\u060c \u06a9\u0646\u062a\u0631\u0644 \u0628\u0631\u062f\u0627\u0634\u062a \u062f\u0631 \u062d\u0648\u0636\u0647 \u0622\u0628\u0631\u06cc\u0632 \u0648 \u062a\u062b\u0628\u06cc\u062a \u06a9\u0627\u0646\u0648\u0646\u200c\u0647\u0627\u06cc \u06af\u0631\u062f\u0648\u063a\u0628\u0627\u0631.",
    "REC_EUTRO": "\u06a9\u0646\u062a\u0631\u0644 \u0648\u0631\u0648\u062f \u067e\u0633\u0627\u0628\u060c \u0645\u062f\u06cc\u0631\u06cc\u062a \u06af\u0648\u0646\u0647\u200c\u0647\u0627\u06cc \u0645\u0647\u0627\u062c\u0645 \u06af\u06cc\u0627\u0647\u06cc (\u0627\u062a\u0631\u0648\u0641\u06cc\u06a9\u0627\u0633\u06cc\u0648\u0646) \u0648 \u062d\u0641\u0638 \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc \u0628\u0627\u0632.",
    "REC_GENERAL": "\u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc \u0641\u0631\u0645 \u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0631\u0627\u0645\u0633\u0631 (RIS) \u0648 \u0627\u0633\u062a\u0645\u0631\u0627\u0631 \u067e\u0627\u06cc\u0634 \u0633\u0631\u06cc\u200c\u0632\u0645\u0627\u0646\u06cc \u0645\u0627\u0647\u0648\u0627\u0631\u0647\u200c\u0627\u06cc."
}

def evaluate_wetland(w, eo_list, docs):
    ramsar_id = w.get("ramsar_id")
    name_en = w.get("name_en", f"Site #{ramsar_id}")
    name_fa = w.get("name_fa") or name_en
    area_ha = float(w.get("area_ha") or 0)

    montreux_cur = str(w.get("montreux_currently_listed") or "").lower() in ("yes", "1", "true")
    montreux_hist = str(w.get("historical_montreux_Mentioned") or "").lower() in ("yes", "1", "true")
    montreux_flag = montreux_cur or montreux_hist

    mgmt_avail = str(w.get("management_plan_available") or "").lower() in ("yes", "1", "true")
    mgmt_plan_flag = mgmt_avail or any("management" in str(d.get("filename","")).lower() for d in docs)

    risk_score = 25
    if montreux_cur: risk_score += 35
    elif montreux_hist: risk_score += 20
    if not mgmt_plan_flag: risk_score += 8

    eo = sorted(eo_list, key=lambda x: (x.get("target_year") or 0, x.get("id") or 0))[-1] if eo_list else None
    has_live_eo = 1 if eo else 0
    water_pct = veg_pct = dry_pct = ndwi_mean = ndvi_mean = scene_date = None

    if eo:
        water_pct = eo.get("water_Ratio_pct")
        veg_pct = eo.get("vegetation_ratio_pct")
        dry_pct = eo.get("dry_or_barren_ratio_pct")
        ndwi_mean = eo.get("mean_ndwi")
        ndvi_mean = eo.get("mean_ndvi")
        scene_date = eo.get("acquisition_date")

        if water_pct is not None:
            if water_pct < 5.0: risk_score += 30
            elif water_pct < 15.0: risk_score += 18
            elif water_pct < 30.0: risk_score += 8
            else: risk_score -= 5

        if veg_pct is not None and water_pct is not None:
            if veg_pct > 30.0 and water_pct < 20.0: risk_score += 12

    risk_score = max(12, min(98, int(risk_score)))

    if risk_score >= 70:
        status_code, status_en, status_fa = "CRITICAL", "Critical / Ecological Character Change (Art. 3.2)", FA["CRITICAL"]
    elif risk_score >= 50:
        status_code, status_en, status_fa = "STRESSED", "High Hydrological & Ecological Stress", FA["STRESSED"]
    elif risk_score >= 35:
        status_code, status_en, status_fa = "MODERATE", "Moderate Stress - Active Monitoring Required", FA["MODERATE"]
    else:
        status_code, status_en, status_fa = "STABLE", "Relatively Stable Ecological Baseline", FA["STABLE"]

    mont_fa = FA["MONTREUX_YES"] if montreux_flag else FA["MONTREUX_NO"]

    if has_live_eo and water_pct is not None:
        summary_en = (
            f"{name_en} (Ramsar #{ramsar_id}, {area_ha:,.0f} ha) exhibits {status_en.lower()}. "
            f"Latest Sentinel-2 L2A pass ({scene_date}) measured {water_pct:.2f}% open surface water "
            f"(mean NDWI={ndwi_mean:.3f}), {veg_pct:.2f}% vegetation (mean NDVI={ndvi_mean:.3f}), and {dry_pct:.2f}% barren/dry bed."
        )
        summary_fa = (
            f"\u062a\u0627\u0644\u0627\u0628 \u00ab{name_fa}\u00bb (\u0633\u0627\u06cc\u062a \u0631\u0627\u0645\u0633\u0631 #{ramsar_id}\u060c \u0645\u0633\u0627\u062d\u062a {area_ha:,.0f} \u0647\u06a9\u062a\u0627\u0631) \u062f\u0631 \u0648\u0636\u0639\u06cc\u062a \u00ab{status_fa}\u00bb \u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f. "
            f"\u0622\u062e\u0631\u06cc\u0646 \u0631\u0635\u062f \u0645\u0627\u0647\u0648\u0627\u0631\u0647 Sentinel-2 (\u0645\u0648\u0631\u062e {scene_date}) \u0646\u0634\u0627\u0646\u200c\u062f\u0647\u0646\u062f\u0647 {water_pct:.2f}% \u067e\u0647\u0646\u0647 \u0622\u0628\u06cc \u0628\u0627\u0632 (NDWI={ndwi_mean:.3f})\u060c "
            f"{veg_pct:.2f}% \u067e\u0648\u0634\u0634 \u06af\u06cc\u0627\u0647\u06cc (NDVI={ndvi_mean:.3f}) \u0648 {dry_pct:.2f}% \u0628\u0633\u062a\u0631 \u062e\u0634\u06a9/\u0634\u0648\u0631\u0647\u200c\u0632\u0627\u0631 \u0627\u0633\u062a. ({mont_fa})"
        )
        rec_en = "Urgent environmental water allocation (e-flow) and Art. 3.2 restoration." if water_pct < 10.0 else "Control nutrient inflow, invasive macrophytes, and sustain seasonal water regime."
        rec_fa = FA["REC_DROUGHT"] if water_pct < 10.0 else (FA["REC_EUTRO"] if veg_pct > 25.0 else FA["REC_GENERAL"])
    else:
        summary_en = f"{name_en} (Ramsar #{ramsar_id}, {area_ha:,.0f} ha) assessed via official Ramsar RIS and COP national dossiers ({status_en}). Ready for on-demand Sentinel-2 pass."
        summary_fa = f"\u062a\u0627\u0644\u0627\u0628 \u00ab{name_fa}\u00bb (\u0633\u0627\u06cc\u062a \u0631\u0627\u0645\u0633\u0631 #{ramsar_id}\u060c {area_ha:,.0f} \u0647\u06a9\u062a\u0627\u0631) \u0628\u0631 \u0627\u0633\u0627\u0633 \u0627\u0633\u0646\u0627\u062f \u0631\u0633\u0645\u06cc RIS \u0648 \u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627\u06cc COP \u062f\u0631 \u0648\u0636\u0639\u06cc\u062a \u00ab{status_fa}\u00bb \u0627\u0631\u0632\u06cc\u0627\u0628\u06cc \u0634\u062f\u0647 \u0627\u0633\u062a ({mont_fa}). \u0622\u0645\u0627\u062f\u0647 \u0641\u0631\u0627\u062e\u0648\u0627\u0646\u06cc \u0632\u0646\u062f\u0647 \u0645\u0627\u0647\u0648\u0627\u0631\u0647 Sentinel-2."
        rec_en = "Schedule on-demand Sentinel-2 L2A pass and update Ramsar Information Sheet (RIS)."
        rec_fa = FA["REC_DROUGHT"] if montreux_flag else FA["REC_GENERAL"]

    evidence = {
        "ramsar_id": ramsar_id,
        "montreux_flagged": montreux_flag,
        "has_management_plan": mgmt_plan_flag,
        "eo_observations_count": len(eo_list),
        "latest_scene_id": eo.get("scene_id") if eo else None,
        "latest_scene_date": scene_date,
        "time_series": [
            {
                "year": r.get("target_year"),
                "date": r.get("acquisition_date"),
                "water_pct": r.get("water_Ratio_pct"),
                "veg_pct": r.get("vegetation_ratio_pct"),
                "dry_pct": r.get("dry_or_barren_ratio_pct"),
                "ndwi": r.get("mean_ndwi"),
                "ndvi": r.get("mean_ndvi")
            } for r in sorted(eo_list, key=lambda x: x.get("target_year") or 0)
        ]
    }

    return {
        "ramsar_id": ramsar_id, "name_en": name_en, "name_fa": name_fa,
        "assessed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_score": risk_score, "status_code": status_code, "status_en": status_en, "status_fa": status_fa,
        "has_live_eo": has_live_eo, "water_ratio_pct": water_pct, "veg_ratio_pct": veg_pct,
        "ndwi_mean": ndwi_mean, "ndvi_mean": ndvi_mean, "summary_en": summary_en, "summary_fa": summary_fa,
        "recommendation_en": rec_en, "recommendation_fa": rec_fa, "evidence": evidence
    }

def run_ai_synthesis():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM wetlands ORDER BY ramsar_id ASC")
    wetlands = [dict(r) for r in cur.fetchall()]

    eo_by_site = {}
    cur.execute("SELECT * FROM satellite_observations")
    for r in cur.fetchall():
        d = dict(r)
        eo_by_site.setdefault(d.get("ramsar_id"), []).append(d)

    docs_by_site = {}
    cur.execute("SELECT * FROM document_catalog")
    for r in cur.fetchall():
        d = dict(r)
        if d.get("related_ramsar_id"):
            docs_by_site.setdefault(d.get("related_ramsar_id"), []).append(d)

    assessments = []
    for w in wetlands:
        rid = w["ramsar_id"]
        res = evaluate_wetland(w, eo_by_site.get(rid, []), docs_by_site.get(rid, []))
        assessments.append(res)
        cur.execute("""
        INSERT OR REPLACE INTO ai_assessments (
            ramsar_id, assessed_at, risk_score, status_code, status_en, status_fa,
            has_live_eo, water_ratio_pct, veg_ratio_pct, ndwi_mean, ndvi_mean,
            summary_en, summary_fa, recommendation_en, recommendation_fa, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            res["ramsar_id"], res["assessed_at"], res["risk_score"], res["status_code"],
            res["status_en"], res["status_fa"], res["has_live_eo"], res["water_ratio_pct"],
            res["veg_ratio_pct"], res["ndwi_mean"], res["ndvi_mean"], res["summary_en"],
            res["summary_fa"], res["recommendation_en"], res["recommendation_fa"],
            json.dumps(res["evidence"], ensure_ascii=False)
        ))

    conn.commit()
    conn.close()

    with open(EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "assessments": assessments}, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] AI Ecological Synthesis updated for {len(assessments)} sites.")
    for a in assessments:
        if a["has_live_eo"]:
            print(f"  * [LIVE EO] #{a['ramsar_id']} {a['name_en'][:26]:26s} | Score: {a['risk_score']}/100 | {a['status_code']:8s} | Water: {a['water_ratio_pct']}% | Veg: {a['veg_ratio_pct']}%")

if __name__ == "__main__":
    run_ai_synthesis()