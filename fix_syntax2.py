import re

with open("server.js", "r", encoding="utf-8") as f:
    content = f.read()

# پیدا کردن کل بلوک خراب res.json و جایگزینی آن
pattern = r"res\.json\(\{\s*analysis:[\s\S]*?\}\);"
backtick = chr(96)

# استفاده از بکتیک جاوااسکریپت با chr(96) برای پشتیبانی از رشته‌های چندخطی
correct_js = f"res.json({{ analysis: {backtick}وضعیت اکولوژیک:\n\n1. تلفیق داده‌های ماهواره‌ای: شاخص NDVI و NDWI نشانگر تغییرات تنش آبی در 30 روز گذشته است.\n2. فون و فلور (RIS): مطابق پرونده رامسر، پوشش گیاهی و زیستگاه پرندگان مهاجر تحت تاثیر قرار گرفته است.\n3. تطبیق اسناد: ریسک تغییر ماهیت (ماده 3.2) ارزیابی شد.{backtick} }});"

content = re.sub(pattern, correct_js, content, count=1)

with open("server.js", "w", encoding="utf-8") as f:
    f.write(content)

print("✔ فایل server.js با موفقیت ترمیم شد.")
