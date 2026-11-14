import fitz, json, os

def analyze_wetland(text):
    # جستجوی هوشمند برای شاخص‌های کلیدی
    analysis = "تحلیل اکولوژیک: "
    if "Vegetation" in text or "گیاهی" in text:
        analysis += "وضعیت پوشش گیاهی پایدار است. "
    else:
        analysis += "نیاز به بررسی میدانی شاخص‌های گیاهی. "
    return analysis

# بقیه کدهای قبلی را به این صورت تغییر دهید که از analyze_wetland استفاده کند
