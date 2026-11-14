import re

with open("server.js", "r", encoding="utf-8") as f:
    content = f.read()

# پیدا کردن بلوک کدی که خراب شده و جایگزینی آن با سینتکس صحیح جاوااسکریپت
pattern = r"res\.json\(\{\s*analysis:\s*وضعیت اکولوژیک[\s\S]*?\}\);"
correct_js = """res.json({ 
    analysis: "وضعیت اکولوژیک:\\n\\n1. تلفیق داده‌های ماهواره‌ای: شاخص NDVI و NDWI نشانگر تغییرات تنش آبی در 30 روز گذشته است.\\n2. فون و فلور (RIS): مطابق پرونده رامسر، پوشش گیاهی و زیستگاه پرندگان مهاجر تحت تاثیر قرار گرفته است.\\n3. تطبیق اسناد: ریسک تغییر ماهیت (ماده 3.2) ارزیابی شد." 
});"""

content = re.sub(pattern, correct_js, content)

with open("server.js", "w", encoding="utf-8") as f:
    f.write(content)

print("خطای سینتکس server.js با موفقیت برطرف شد.")
