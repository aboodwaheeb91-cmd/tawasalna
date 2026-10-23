## PR AUD-P2-49 — ترتيب الخبرات بـ sort_order + شيل زر «حفظ الوظيفة» الوهمي — 2026-10-23
- السبب الجذري (الخبرات): عمود `experience.sort_order` كان بينضاف بـ `DEFAULT 0` وما بينعبّى، فكل الصفوف متساوية والترتيب الفعلي كان من `id DESC`؛ الإضافة كانت بـ 0 فبتتساوى مع أول خبرة بعد أي إعادة ترتيب.
- `auth._migrate_experience_sort_order` (startup migration `experience_sort_order`، حرجة): العمود `IF NOT EXISTS` + backfill لمرة وحدة (`app_migrations`) بنفس الترتيب المعروض (`sort_order ASC, id DESC`) → 0..n-1 لكل مستخدم + `NOT NULL` + index `(user_id, sort_order, id)`. انشال الـ `ALTER` اللي كان بيبلع خطأه بـ `init_db`. RLS ما تغيّر.
- الـ API: `ORDER BY sort_order ASC, id ASC` (ثانوي ثابت) · خبرة جديدة = `MAX(sort_order)+1` (آخر القائمة) · `reorder_experience` بـ transaction وحدة (التحقق من الملكية كان موجود: id مش إلك / مكرر → 403).
- الواجهة: الخبرة الجديدة بتنحط بآخر القائمة (`push` بدل `unshift`) — نفس ترتيب السيرفر.
- زر «حفظ الوظيفة» انشال (قرار منتج — الميزة لاحقاً): `job-detail.html` (بطاقة التقديم + الشريط اللاصق) + `toggleSave` + CSS `.jd-save-btn` / `.jd-sticky-save` · كروت وظائف صفحة الشركة (`vjc-btn--save` + handler + CSS) · مفاتيح `job.save` / `job.save_label` / `job.save_soon`. بدون جدول أو endpoint.
- اختبار: `python -m pytest tests/test_experience_sort_order_49.py -q`.
