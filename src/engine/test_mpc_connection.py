import sys
import requests
import pystac_client
import planetary_computer

def run_test():
    print("--- [Test 1] Connecting to Microsoft Planetary Computer STAC API (Keyless) ---")
    stac_url = "https://planetarycomputer.microsoft.com/api/stac/v1"
    try:
        catalog = pystac_client.Client.open(
            stac_url,
            modifier=planetary_computer.sign_inplace,
        )
        print("SUCCESS: Connected to STAC API.")
    except Exception as e:
        print(f"FAILED to connect to STAC API: {e}")
        sys.exit(1)

    print("\n--- [Test 2] Searching Sentinel-2 L2A for Lake Urmia (Sample Point) ---")
    # Sample bounding box around central Lake Urmia
    bbox = [45.20, 37.50, 45.50, 37.80]
    try:
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime="2024-06-01/2024-09-01",
            query={"eo:cloud_cover": {"lt": 10}},
            max_items=1
        )
        items = list(search.get_items())
        if not items:
            print("WARNING: No items found for this query.")
            sys.exit(0)
        item = items[0]
        print(f"SUCCESS: Found Scene ID: {item.id}")
        print(f"         Acquisition Date: {item.datetime}")
        print(f"         Cloud Cover: {item.properties.get('eo:cloud_cover')}%")
    except Exception as e:
        print(f"FAILED during STAC search: {e}")
        sys.exit(1)

    print("\n--- [Test 3] Verifying Anonymous SAS Token & Direct Asset Reachability (Zero Download) ---")
    try:
        # Check Band 3 (Green) and Band 8 (NIR) used for NDWI
        b03_href = item.assets["B03"].href
        has_token = "sig=" in b03_href and "se=" in b03_href
        print(f"Anonymous SAS Token attached automatically: {has_token}")
        
        # Send HTTP HEAD request (reads headers only, 0 MB image download)
        resp = requests.head(b03_href, timeout=15)
        print(f"Asset HTTP Status Code: {resp.status_code}")
        if resp.status_code in (200, 206):
            size_mb = int(resp.headers.get("Content-Length", 0)) / (1024 * 1024)
            print(f"SUCCESS: Asset is directly reachable! (Full band size on server: {size_mb:.2f} MB - NOT downloaded)")
            print("Range requests supported:", resp.headers.get("Accept-Ranges", "unknown"))
        else:
            print(f"WARNING: Unexpected HTTP status: {resp.status_code}")
    except Exception as e:
        print(f"FAILED to reach asset storage: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
