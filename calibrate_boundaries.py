import json
import os

geojson_file = 'iran_ramsar_exact_boundaries.geojson'

# مختصات رسمی (طول و عرض جغرافیایی) بر اساس فایل‌های RIS
# Urmia: 37°30'N 045°30'E -> [45.5, 37.5]
# Shadegan: 30°30'N 048°40'E -> [48.666, 30.5]
# Hamun-e-Saberi & Helmand: 31°20'N 061°20'E -> [61.333, 31.333]
# Hamun-e-Puzak: 31°20'N 061°45'E -> [61.75, 31.333]

corrections = {
    'Urmia': [45.5, 37.5],
    'Shadegan': [48.666, 30.5],
    'Hamun-e-Saberi': [61.333, 31.333],
    'Hamun-e-Puzak': [61.75, 31.333]
}

if not os.path.exists(geojson_file):
    print(f"Error: {geojson_file} not found!")
else:
    with open(geojson_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    for feature in data.get('features', []):
        props = feature.get('properties', {})
        name = props.get('english_name', '') + " " + props.get('official_name', '')
        
        for key, correct_coords in corrections.items():
            if key in name:
                # اصلاح مختصات برای حالت Point (در صورت نیاز به چندضلعی، هندسه باید کامل جایگزین شود)
                if feature.get('geometry', {}).get('type') == 'Point':
                    feature['geometry']['coordinates'] = correct_coords
                    updated_count += 1
                    print(f"✔ مختصات {key} با موفقیت اصلاح شد.")

    if updated_count > 0:
        with open(geojson_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("فایل iran_ramsar_exact_boundaries.geojson با موفقیت کالیبره و ذخیره شد.")
    else:
        print("هیچ تالابی برای اصلاح یافت نشد یا مختصات قبلاً از نوع Point نبوده است.")
