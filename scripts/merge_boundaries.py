# -*- coding: utf-8 -*-
"""Merge/verify 28 Ramsar wetland boundaries into a single EPSG:4326 GeoJSON."""
import json
import os
import sys
from pathlib import Path

try:
    import geopandas as gpd
    from shapely.geometry import mapping
    from shapely.validation import make_valid
except Exception as e:
    print("geopandas/shapely not available:", e)
    sys.exit(1)

BASE = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [
    Path("/mnt/data/ramsar_work/nested"),
    Path("/mnt/data/.tmp_ramsar"),
    Path("/mnt/data/.inspect_sites_tmp"),
    Path("/mnt/data"),
    BASE / ".tmp_ramsar",
    BASE / ".inspect_sites_tmp",
    BASE / "data" / "authoritative_boundaries",
    BASE / "data" / "boundaries",
]
ID_CANDIDATES = ["ramsar_id", "ramsarid", "site_id", "id", "code", "OBJECTID", "FID", " Ramsar"]

def find_shapefiles():
    shps = []
    for root in SEARCH_ROOTS:
        if root.exists():
            shps.extend(root.rglob("*.shp"))
    # dedupe
    seen = set()
    out = []
    for p in shps:
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out

def detect_id_column(df):
    for c in ID_CANDIDATES:
        if c in df.columns:
            return c
    # fallback: first column that looks like id
    for c in df.columns:
        if "id" in c.lower() or "code" in c.lower():
            return c
    return None

def normalize_id(v):
    try:
        return int(float(str(v).replace("IR", "").strip()))
    except Exception:
        s = str(v).strip()
        return s

def main():
    shps = find_shapefiles()
    frames = []
    if shps:
        print(f"Found {len(shps)} shapefile(s)")
        for shp in shps:
            try:
                gdf = gpd.read_file(shp)
                if gdf.crs is None:
                    gdf = gdf.set_crs("EPSG:4326")
                else:
                    gdf = gdf.to_crs("EPSG:4326")
                id_col = detect_id_column(gdf)
                if id_col is None:
                    print(f"  skip (no id col): {shp}")
                    continue
                gdf = gdf.rename(columns={id_col: "ramsar_id"})
                gdf["ramsar_id"] = gdf["ramsar_id"].apply(normalize_id)
                # keep only geometry + ramsar_id
                gdf = gdf[["ramsar_id", "geometry"]].copy()
                # fix geometries
                gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if g is not None else g)
                gdf = gdf[gdf.geometry.notnull()]
                frames.append(gdf)
                print(f"  loaded {len(gdf)} features from {shp.name}")
            except Exception as e:
                print(f"  error reading {shp}: {e}")
    else:
        print("No shapefiles found; falling back to existing GeoJSON.")

    if frames:
        merged = gpd.GeoDataFrame(pd_concat(frames), crs="EPSG:4326") if False else None
        import pandas as pd
        merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
        # dissolve multiple parts per site
        merged = merged.dissolve(by="ramsar_id", as_index=False)
        merged["ramsar_id"] = merged["ramsar_id"].apply(normalize_id)
    else:
        # fallback: load existing geojson
        existing = None
        for cand in [BASE / "data" / "iran_ramsar_exact_boundaries.geojson",
                     BASE / "frontend" / "public" / "data" / "iran_ramsar_exact_boundaries.geojson"]:
            if cand.exists():
                existing = cand
                break
        if existing is None:
            print("No existing GeoJSON found; aborting.")
            sys.exit(1)
        merged = gpd.read_file(existing)
        if merged.crs is None:
            merged = merged.set_crs("EPSG:4326")
        else:
            merged = merged.to_crs("EPSG:4326")
        if "ramsar_id" not in merged.columns:
            # try detect
            for c in merged.columns:
                if "ramsar" in c.lower() or c.lower() == "id":
                    merged = merged.rename(columns={c: "ramsar_id"})
                    break
        merged["ramsar_id"] = merged["ramsar_id"].apply(normalize_id)
        merged["geometry"] = merged["geometry"].apply(lambda g: make_valid(g) if g is not None else g)
        merged = merged[merged.geometry.notnull()]

    # validate count
    print(f"Merged feature count: {len(merged)}")
    # ensure properties include ramsar_id (int where possible)
    merged = merged[["ramsar_id", "geometry"]]

    out_path = BASE / "data" / "iran_ramsar_exact_boundaries.geojson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_file(out_path, driver="GeoJSON")
    # also copy to frontend
    fe_path = BASE / "frontend" / "public" / "data" / "iran_ramsar_exact_boundaries.geojson"
    fe_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_file(fe_path, driver="GeoJSON")
    print(f"Written: {out_path}")
    print(f"Written: {fe_path}")

if __name__ == "__main__":
    main()
