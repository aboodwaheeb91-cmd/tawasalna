# Content Screens Backend — النصوص · الألوان · الأخبار (phase 5a)

> Spec: `docs/SYSTEMS_INDEX.md §25h` · `ARCHITECTURE.md §79` · test `python -m pytest tests/test_content_admin_5a.py -q`

1. **الصلاحية `content.edit`** (`server.CONTENT_PERM`) على كل قراءة وكتابة بـ `/admin/strings` · `/admin/theme/colors` · `/admin/news` عبر `check_admin(request, CONTENT_PERM)` — نفس نمط `settings.edit`: بدون توكن / توكن غلط → 401 · أدمن بدون الصلاحية → 403. الأدمن الرئيسي `perms: ["*"]`.
2. **السجل:** صف `admin_audit_middleware` الواحد (العملية · الفاعل · النتيجة) + الهدف عبر `request.state.audit_target`: `keys=…` (النصوص) · `tokens=…` (الألوان) · `news_id=…` (الأخبار). ❌ تخزين النص / اللون / محتوى الخبر بالسجل.
3. **الألوان:** الـ PUT بيقبل `theme_tokens.EDITABLE` بس (`--color-brand-primary` · `--color-brand-accent`) وقيمة `#RRGGBB` بس → غير هيك 400. الـ overrides القديمة لتوكنات تانية بتضل محفوظة وبيطبّقها `/theme.css`. ❌ حذفها عند الحفظ.
4. **الأخبار:** `starts_at` / `ends_at` (`TIMESTAMPTZ NULL`، `ends_at > starts_at` وإلا 400). «نشط» = `server.NEWS_ACTIVE_SQL` بس — الفيد و `/news/banner`. ❌ شرط «نشط» تاني.
5. **`GET /news/banner`** عام بدون دخول: أحدث خبر نشط أو `null`، حقول `id` · `title` · `summary` · `source_url` بس (رابط مش http/https → `null`). ❌ حقول داخلية · ❌ مسودة / مؤرشف / مجدول / منتهي.
