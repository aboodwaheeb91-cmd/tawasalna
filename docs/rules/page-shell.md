# Page Shell V1 (DS-SHELL)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتنشئ صفحة HTML أو بتعدّل الـ `<head>` / السكربتات المشتركة.
> القاعدة العليا: `ARCHITECTURE_FOUNDATION.md` → F39. المواصفة الكاملة: `docs/design-system/PAGE-SHELL.md` (SHELL-00 → SHELL-08).

## Page Shell Rules (mandatory for all AI sessions)

1. **مصدر واحد:** `page_shell.py` + `partials/shell-*.html`، مستدعى من `read_html()` بـ `server.py`. أي meta / font / ملف مشترك لكل الصفحات → بالـ partial، مش بالصفحات.

2. **Markers:** `<!--tw:shell-head-->` أول سطر بعد `<head>` · `<!--tw:shell-scripts-->` قبل سكربتات الصفحة. أدمن: `<!--tw:shell-head:admin-->` / `<!--tw:shell-scripts:admin-->`. نسخة وحدة، كل marker مرة وحدة — غير هيك `ValueError`.

3. **صفحة بدون markers ما بتتغيّر** (مطابقة بالبايت). التحويل صفحة صفحة فقط (المرحلة C) مع screenshots قبل/بعد (موبايل + ديسكتوب)؛ أي فرق بصري يُذكر ويُبرَّر.

4. **الترتيب:** `tw_shared.css` قبل CSS الصفحة · `/static/tw_shared.js` ← `auth-sync.js` ← سكربتات الصفحة (`/tw_shared.js` القديم بيضل للصفحات غير المحوّلة — نفس الملف).

5. **`?v=H`** للملفات المشتركة = hash المحتوى عند بدء السيرفر. ممنوع `?v=` يدوي لـ `tw_shared.*` / `auth-sync.js`.

6. **الأدمن:** بدون `manifest`، بدون `auth-sync.js`، و `<meta name="tw-sw" content="off">` (ما في تسجيل SW).

7. **الأمان (§54):** الحقن نص ثابت فقط — ممنوع أي بيانات مستخدم أو request بالـ partials.

8. **ممنوع:** `tw-icons.js` بالـ shell (F37) · `user-scalable=no` · آلية حقن / partial ثانية · خدمة `partials/` مباشرة · نسخ tags الـ shell يدوياً بصفحة محوّلة.

9. **اختبار قديم بيقرأ صفحة محوّلة كملف خام** → حدّثه ليقرأ `apply_shell(...)` (ناتج `read_html`).

Test: `python test_page_shell.py`.
