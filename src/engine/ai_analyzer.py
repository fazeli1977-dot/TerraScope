# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import sys
from pathlib import Path

def _base_dir():
    for p in Path(__file__).resolve().parents:
        if (p / "data" / "database" / "terrascope.db").exists():
            return p
    # default: two levels up (scripts) or three (src/engine)
    return Path(__file__).resolve().parents[1]

BASE_DIR = _base_dir()
DB_PATH = BASE_DIR / "data" / "database" / "terrascope.db"


def connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def find_wetland(conn, key):
    cur = conn.cursor()
    key = str(key).strip()
    # numeric id
    if key.isdigit():
        cur.execute("SELECT * FROM wetlands WHERE ramsar_id = ? OR id = ? LIMIT 1", (key, key))
        row = cur.fetchone()
        if row:
            return dict(row)
    # name search
    cur.execute(
        "SELECT * FROM wetlands WHERE name_en LIKE ? OR name_fa LIKE ? LIMIT 1",
        (f"%{key}%", f"%{key}%"),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    # fallback first
    cur.execute("SELECT * FROM wetlands ORDER BY ramsar_id ASC LIMIT 1")
    row = cur.fetchone()
    return dict(row) if row else None


def latest_observation(conn, ramsar_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM satellite_observations WHERE ramsar_id = ? ORDER BY COALESCE(observation_date, date) DESC LIMIT 1",
        (ramsar_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def assessment(conn, ramsar_id):
    cur = conn.cursor()
    # ai_assessments
    try:
        cur.execute("SELECT * FROM ai_assessments WHERE ramsar_id = ? LIMIT 1", (ramsar_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
    except Exception:
        pass
    # ecological_ai_assessments
    try:
        cur.execute("SELECT * FROM ecological_ai_assessments WHERE ramsar_id = ? LIMIT 1", (ramsar_id,))
        row = cur.fetchone()
        if row:
            d = dict(row)
            return {
                "risk_score": d.get("risk_score"),
                "status_code": d.get("ecological_status_code"),
                "status_en": d.get("ecological_status_code"),
                "status_fa": d.get("ecological_status_code"),
                "summary_fa": d.get("summary_fa"),
                "summary_en": d.get("summary_en"),
                "ai_analysis_fa": d.get("summary_fa"),
                "ai_analysis_en": d.get("summary_en"),
                "recommendation_fa": d.get("recommendations_fa"),
                "recommendation_en": d.get("recommendations_en"),
            }
    except Exception:
        pass
    return {}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    key = sys.argv[1] if len(sys.argv) > 1 else ""
    lang = sys.argv[2] if len(sys.argv) > 2 else "fa"
    if not DB_PATH.exists():
        print(json.dumps({"status": "error", "message": f"DB not found: {DB_PATH}"}, ensure_ascii=False))
        return
    conn = connect()
    w = find_wetland(conn, key)
    if not w:
        print(json.dumps({"status": "error", "message": "Wetland not found"}, ensure_ascii=False))
        conn.close()
        return
    rid = w.get("ramsar_id")
    obs = latest_observation(conn, rid)
    a = assessment(conn, rid)
    conn.close()

    risk = a.get("risk_score")
    if risk is None and obs:
        risk = obs.get("risk_score")
    name_en = w.get("name_en") or f"Site {rid}"
    name_fa = w.get("name_fa") or name_en
    analysis_fa = a.get("ai_analysis_fa") or a.get("summary_fa") or ""
    analysis_en = a.get("ai_analysis_en") or a.get("summary_en") or ""
    rec_fa = a.get("recommendation_fa") or ""
    rec_en = a.get("recommendation_en") or ""
    status_code = a.get("status_code") or ("CRITICAL" if (risk or 0) >= 70 else "MONITORED")

    # If no stored assessment, synthesize a concise local analysis from metrics
    if not analysis_fa and not analysis_en:
        water = obs.get("water_ratio_pct") if obs else None
        veg = obs.get("veg_ratio_pct") if obs else None
        dry = obs.get("dry_ratio_pct") if obs else None
        ndwi = obs.get("ndwi_mean") if obs else None
        ndvi = obs.get("ndvi_mean") if obs else None
        analysis_fa = (
            f"تحلیل اکولوژیک محلی (TerraScope) برای {name_fa} (رامسر #{rid}): "
            f"بر اساس آخرین رصد Sentinel-2، پهنه آبی {water}%، پوشش گیاهی {veg}%، بستر خشک {dry}%، "
            f"NDWI={ndwi} و NDVI={ndvi}. امتیاز ریسک ترکیبی: {risk}. وضعیت: {status_code}."
        )
        analysis_en = (
            f"Local ecological analysis (TerraScope) for {name_en} (Ramsar #{rid}): "
            f"Latest Sentinel-2 EO shows open water {water}%, vegetation {veg}%, dry bed {dry}%, "
            f"NDWI={ndwi}, NDVI={ndvi}. Composite risk score: {risk}. Status: {status_code}."
        )
        rec_fa = "1. تداوم پایش ماهواره‌ای فصلی؛ 2. کنترل فشارهای انسانی و حقابه محیط‌زیستی؛ 3. به‌روزرسانی RIS."
        rec_en = "1. Maintain seasonal EO monitoring; 2. Manage anthropogenic pressures and environmental flows; 3. Update RIS."

    out = {
        "status": "success",
        "ramsar_id": rid,
        "name_en": name_en,
        "name_fa": name_fa,
        "risk_score": risk,
        "status_code": status_code,
        "status_en": a.get("status_en") or status_code,
        "status_fa": a.get("status_fa") or status_code,
        "analysis": analysis_fa if lang == "fa" else analysis_en,
        "analysis_fa": analysis_fa,
        "analysis_en": analysis_en,
        "recommendation_fa": rec_fa,
        "recommendation_en": rec_en,
        "observation_date": obs.get("observation_date") if obs else None,
        "citations": [
            {"type": "static", "source": f"Ramsar RIS IR{rid}", "section": "RIS", "date": w.get("designation_date")},
            {"type": "live", "source": "Sentinel-2 EO Data", "date": obs.get("observation_date") if obs else None}
        ]
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
