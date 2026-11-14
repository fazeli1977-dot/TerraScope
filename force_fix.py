import re
import os

app_path = "public/app.js"
if not os.path.exists(app_path):
    app_path = "app.js"
if not os.path.exists(app_path):
    app_path = "frontend/public/app.js"

with open(app_path, "r", encoding="utf-8") as f:
    js = f.read()

# 1. جایگزینی رسم مستطیل و زوم ثابت با خواندن GeoJSON و زوم دقیق (fitBounds)
old_map_logic = r"map\.flyTo\(\[Number\(w\.latitude\),\s*Number\(w\.longitude\)\],\s*9,\s*\{\s*duration:\s*1\.1\s*\}\);\s*if\s*\(bboxLayer\)\s*\{\s*bboxLayer\.clearLayers\(\);\s*\}\s*if\s*\(w\.bbox\)[\s\S]*?addTo\(bboxLayer\);\s*\}"

new_map_logic = """
    // پاک کردن مرز قبلی
    if (bboxLayer) { bboxLayer.clearLayers(); }
    
    // بارگذاری فایل GeoJSON و زوم دقیق روی مرز تالاب
    fetch('iran_ramsar_exact_boundaries.geojson')
        .then(res => res.json())
        .then(geoData => {
            const wetlandFeature = geoData.features.find(f => f.properties.name === w.name_en || f.properties.id === w.ramsar_id);
            if (wetlandFeature) {
                const geoLayer = L.geoJSON(wetlandFeature, {
                    style: { color: '#00ffff', weight: 2, fillOpacity: 0.2 }
                }).addTo(bboxLayer);
                map.fitBounds(geoLayer.getBounds(), { padding: [50, 50], maxZoom: 12 });
            } else {
                // اگر مرز دقیق پیدا نشد، به همان نقطه زوم کن
                map.flyTo([Number(w.latitude), Number(w.longitude)], 10, { duration: 1.1 });
            }
        }).catch(err => {
            console.error("خطا در بارگذاری نقشه مرزها:", err);
            map.flyTo([Number(w.latitude), Number(w.longitude)], 10, { duration: 1.1 });
        });
"""
js = re.sub(old_map_logic, new_map_logic, js)

# 2. اصلاح کش شدن پاسخ هوش مصنوعی (افزودن timestamp به درخواست)
js = js.replace("fetch('/api/ai-analysis?name=' + encodeURIComponent(wetlandName));", "fetch('/api/ai-analysis?name=' + encodeURIComponent(wetlandName) + '&t=' + new Date().getTime());")

with open(app_path, "w", encoding="utf-8") as f:
    f.write(js)

print("✅ فایل app.js با موفقیت بازنویسی و منطق زوم (fitBounds) اضافه شد.")
