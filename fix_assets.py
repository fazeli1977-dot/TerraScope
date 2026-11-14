import os, glob
from PIL import Image, ImageGrab

os.makedirs('docs/assets', exist_ok=True)

# گرفتن اسکرین‌شات از صفحه فعلی یا کراپ فایل‌های موجود
files = sorted(glob.glob('image*.webp') + glob.glob('image*.png') + glob.glob('image*.jpg'))
count = 1

if files:
    for f in files:
        try:
            img = Image.open(f)
            w, h = img.size
            if w > 800 and h > 500:
                box = (0, 135, w, h - 55) if h > 700 else (0, 0, w, h)
                cropped = img.crop(box)
                out_path = f"docs/assets/preview_{count}.png"
                cropped.save(out_path, "PNG")
                print(f"✅ Generated image: {out_path}")
                count += 1
                if count > 3: break
        except Exception:
            pass

# اگر فایلی در ریشه نبود، اسکرین‌شات زنده می‌گیرد
if count == 1:
    try:
        shot = ImageGrab.grab()
        w, h = shot.size
        cropped = shot.crop((0, 135, w, h - 55))
        for i in range(1, 4):
            path = f"docs/assets/preview_{i}.png"
            cropped.save(path, "PNG")
            print(f"✅ Screenshot saved: {path}")
    except Exception as e:
        print(f"Error grabbing screen: {e}")

# update README links
readme_path = "README.md"
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    content = content.replace("docs/assets/dashboard_preview.png", "docs/assets/preview_1.png")
    content = content.replace("docs/assets/ai_analysis.png", "docs/assets/preview_2.png")
    content = content.replace("docs/assets/gis_mapping.png", "docs/assets/preview_3.png")
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ README.md links updated!")
