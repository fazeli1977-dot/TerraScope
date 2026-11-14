import os
from PIL import Image

os.makedirs('docs/assets', exist_ok=True)

# لیست تصاویری که داشبورد برنامه TerraScope را نشان می‌دهند
candidate_files = [
    'image-(98).webp', 'image-(96).webp', 'image-(92).webp', 
    'image-(88).webp', 'image-(85).webp', 'image-(84).webp', 
    'image-(63).webp', 'image-(45).webp', 'image-(34).webp'
]

found = []
for f in candidate_files:
    if os.path.exists(f):
        found.append(f)

if not found:
    # جستجوی عمومی در صورت تغییر نام فایل‌ها
    import glob
    found = sorted(glob.glob('image*.webp') + glob.glob('image*.png'))

print(f"📷 یافت شده برای کراپ داشبورد: {found[:3]}")

count = 1
for f in found[:3]:
    try:
        img = Image.open(f)
        w, h = img.size
        # کراپ دقیق داشبورد (حذف نوار ابزار بالا و پایین مرورگر)
        box = (0, 75, w, h - 40) if h > 600 else (0, 0, w, h)
        cropped = img.crop(box)
        
        out_path = f"docs/assets/preview_{count}.png"
        cropped.save(out_path, "PNG")
        print(f"✅ تصویر داشبورد آماده شد: {out_path}")
        count += 1
    except Exception as e:
        print(f"خطا در پردازش {f}: {e}")

# به‌روزرسانی مسیرها در README.md
readme_path = "README.md"
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    content = content.replace("docs/assets/dashboard_preview.png", "docs/assets/preview_1.png")
    content = content.replace("docs/assets/ai_analysis.png", "docs/assets/preview_2.png")
    content = content.replace("docs/assets/gis_mapping.png", "docs/assets/preview_3.png")
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ فایل README.md با لینک‌های جدید به‌روز شد.")
