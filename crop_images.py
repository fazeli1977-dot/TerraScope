import os
import glob
from PIL import Image

os.makedirs('docs/assets', exist_ok=True)
# یافتن اسکرین‌شات‌ها
files = sorted(glob.glob('image*.webp') + glob.glob('image*.png') + glob.glob('image*.jpg'))

count = 1
for f in files:
    try:
        img = Image.open(f)
        w, h = img.size
        if w > 1000 and h > 600: # تفکیک اسکرین‌شات‌ها از آیکون‌ها
            box = (0, 135, w, h - 55) # حذف مرورگر و تسک‌بار
            cropped = img.crop(box)
            out_path = f"docs/assets/preview_{count}.png"
            cropped.save(out_path, "PNG")
            print(f"✅ Cropped & saved: {out_path}")
            count += 1
            if count > 3: break
    except Exception as e:
        pass
