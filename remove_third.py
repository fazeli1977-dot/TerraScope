import os

# ویرایش README.md برای حذف تصویر سوم
readme_path = "README.md"
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # حذف بخش مربوط به تصویر سوم از فایل مستندات
    # فرض بر این است که پpreview_3 در اواخر فایل یا بخش جداگانه قرار دارد
    lines = content.splitlines()
    new_lines = []
    skip = False
    for line in lines:
        if "preview_3.png" in line or "Exact Boundary Mapping" in line:
            skip = True
        if skip and ("##" in line and "Exact Boundary" not in line):
            skip = False
        if not skip:
            new_lines.append(line)
            
    # اگر با جایگزین ساده هم حل شود:
    clean_content = "\n".join(new_lines)
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(clean_content)
    print("✅ فایل README.md پاکسازی و تصویر سوم از آن حذف شد.")

# حذف فایل فیزیکی تصویر سوم از پوشه assets
p3_path = "docs/assets/preview_3.png"
if os.path.exists(p3_path):
    os.remove(p3_path)
    print("🗑️ تصویر سوم (preview_3.png) به طور کامل حذف شد.")
