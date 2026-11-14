import os, time
from PIL import Image, ImageGrab

os.makedirs('docs/assets', exist_ok=True)
print("⏳ 3 ثانیه فرصت دارید مرورگر (داشبورد برنامه) را باز کنید...")
time.sleep(3)

# گرفتن اسکرین‌شات مستقیم از داشبورد روی مانیتور
shot = ImageGrab.grab()
w, h = shot.size
box = (0, 135, w, h - 55) # حذف مرورگر و تسک‌بار
cropped = shot.crop(box)

for i in range(1, 4):
    path = f"docs/assets/preview_{i}.png"
    cropped.save(path, "PNG")
    print(f"✅ Dashboard screenshot saved: {path}")
