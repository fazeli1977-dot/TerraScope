import os
from PIL import Image

os.makedirs('docs/assets', exist_ok=True)

# فایل‌های ورودی که شما در پوشه پروژه ذخیره کردید
files = ['1.png', '2.png', '3.png']

for i, file_name in enumerate(files, start=1):
    if os.path.exists(file_name):
        try:
            img = Image.open(file_name)
            w, h = img.size
            # کراپ دقیق: 115 پیکسل از بالا (مرورگر) و 50 پیکسل از پایین (تسک‌بار ویندوز) حذف می‌شود
            box = (0, 115, w, h - 50)
            cropped = img.crop(box)
            out_path = f"docs/assets/preview_{i}.png"
            cropped.save(out_path, "PNG")
            print(f"✅ تصویر {file_name} به زیبایی کراپ و در {out_path} ذخیره شد.")
        except Exception as e:
            print(f"❌ خطا در کراپ {file_name}: {e}")
    else:
        print(f"⚠️ فایل {file_name} پیدا نشد! مطمئن شوید عکس‌ها را دقیقاً با نام‌های 1.png, 2.png, 3.png در پوشه پروژه ذخیره کرده‌اید.")

# بروزرسانی لینک‌های README.md
readme_path = "README.md"
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    content = content.replace("docs/assets/dashboard_preview.png", "docs/assets/preview_1.png")
    content = content.replace("docs/assets/ai_analysis.png", "docs/assets/preview_2.png")
    content = content.replace("docs/assets/gis_mapping.png", "docs/assets/preview_3.png")
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ لینک‌های فایل README.md با موفقیت تنظیم شدند.")
