# Admin Shell (task 5.3a)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتلمس صفحة أدمن (`admin.html` · `admin-email.html` · `admin-view.html` من 5.3b).
> المواصفة: `docs/SYSTEMS_INDEX.md` §25a · جلسة الأدمن: §25 + `docs/rules/auth-identity.md → Admin Authentication`.

## Admin Shell Rules (mandatory for all AI sessions)

1. **هيدر + قائمة وحدة لكل صفحات الأدمن:** `<header data-tw-header="admin" hidden></header>` أول عنصر بالـ `<body>` + `TwAdminShell.mount()` (`static/shared/admin-shell.js`). `twMountAppChrome` بيتجاهل هالـ variant. ❌ هيدر / قائمة / تبويبات خاصة بصفحة أدمن.

2. **القائمة من registry واحد:** `TW_ADMIN_SECTIONS` بـ `static/shared/admin-sections.js` — كل قسم = `{key, icon (DS-ICON), labelKey (twT), path, badge?}`. `path` نسبي لجذر اللوحة: `''` الجذر · `'#x'` قسم من صفحة الجذر (`admin.html` بتعرض `[data-adm-section="x"]`) · `'name'` صفحة فرعية (route بـ `server.py` = جذر اللوحة + `/name`). قسم جديد = سطر بالـ registry + مفتاح نص؛ صفحة فرعية جديدة = كمان route + ملف HTML.

3. **ممنوع الـ slug أو `tw-ctrl-` بأي ملف بيوصل للمتصفح.** جذر اللوحة بينقرى وقت التشغيل من أول جزء بـ `location.pathname` (`TwAdminShell.base()`)، والدخول بيروح لـ `<جذر اللوحة>/login` (نفس `admin_login`). لصفحة برّا اللوحة (`admin-view.html`): `TwAdminSession.panelHref()` (sessionStorage لنفس التاب). فحص: `tests/test_page_shell_security.py` + `tests/test_admin_shell_runtime.js` (B).

4. **بوابة الجلسة — نداء واحد أول سكربت الصفحة:** `TwAdminShell.start({loginPage})` → `true` = جلسة حيّة؛ ما في جلسة → صفحة الدخول بتعرض نموذجها / أي صفحة تانية `location.replace(جذر اللوحة)`.

5. **انتهاء الجلسة (401 / 403 / exp) من مكان واحد:** `TwAdminShell` بيسجّل handler واحد على `TwAdminSession.onExpired` → `location.replace(جذر اللوحة + '?session=expired')` → صفحة الدخول بتعرض `admin.session.expired`. ❌ handler تاني بصفحة · ❌ فحص `r.status === 401` يدوي.

6. **كل تعديل بيانات عبر `TwAdminShell.run(action, ctx)`:** `action = {confirm?, request(ctx) → {url, method, body?}, done?, fail?}`. ما في تأكيد → ما في طلب. كل إجراء كبير (حذف، تغيير نوع حساب، تغيير كلمة سر، رفض توثيق، حل بلاغ، صيانة، استبدال الشعار) إلو `confirm` بنص بيوضّح شو رح يصير (`admin.*` بـ `tw_strings.json`). الأخطر (حذف، ترحيل/صيانة) `danger: true` + `typeWord` → نافذة `twModal` زر التأكيد فيها مطفّي لحد ما تنكتب الكلمة. ❌ `TwAdminSession.fetch` مباشر لعملية كتابة بصفحة أدمن.

7. **كل كرت / قسم إلو زر ⓘ:** `TwAdminShell.card(parent, {titleKey, hintKey, icon})` — جملة بسيطة بتشرح شو بيعمل القسم. ❌ نمط كرت-مع-ⓘ تاني.

8. **شارات الأعداد جزء من الـ shell:** `badge` بالـ registry (`reports` = بلاغات `pending` · `kyc` = طلبات `review`)؛ الصفحة بتنادي `TwAdminShell.refreshBadges()` بعد إجراء بيغيّر العدد.

9. **الصفحة نفسها:** Page Shell أدمن (`<!--tw:shell-head:admin-->` / `<!--tw:shell-scripts:admin-->`) · ترتيب السكربتات: `admin-session.js` → `tw-icons.js` → `tw-overlay.js` → `admin-sections.js` → `admin-shell.js` → سكربت الصفحة · ألوان `--color-*` بس (`admin-shell.css` + CSS الصفحة) · نص `twT` · أيقونات DS-ICON · نوافذ DS-OVL · `page_audit` = صفر.

10. **الإطار (task 5.3a2):** ديسكتوب (≥ 1024px) = قائمة جانبية ثابتة يمين بلون `--color-brand-primary` + شريط علوي · موبايل = الشريط العلوي + زر القائمة → `TwAdminShell.openMenu()` = نفس روابط الـ registry جوّا `twModal` (DS-OVL — ما في drawer preset بالـ runtime) وبتسكّر لما تختار رابط. الشريط العلوي: بحث موحّد (`searchResults` — مستخدمين / شركات / وظائف من `GET /auth/users` + `GET /admin/jobs`) · حالة النظام (`TwAdminShell.health()` من `/health`) · اختصارات الشارات · خروج. ❌ قائمة / بحث / مؤشر حالة تاني بصفحة أدمن.

11. **الشركات = نفس جدول المستخدمين بفلتر نوع ثابت** (`VIEWS.companies` بـ `admin.js`). ❌ كود جدول تاني لنوع حساب.

12. **لوحة القيادة = بيانات حقيقية بس (F30):** كل كرت / رسم / طابور إلو endpoint حقيقي (`GET /admin/stats/summary` · `/admin/stats/timeseries` · `/admin/activity` · `/admin/kyc` · `/admin/reports` · `/health` · `/admin/audit`). عنصر ما إلو بيانات بالموقع (إيرادات، اشتراكات، مدفوعات، إعلانات، تقييمات، دعم فني، تذاكر) → **ما بيظهر أبداً** — لا رقم وهمي ولا قسم فاضي — ومسجّل بـ `docs/FUTURE_ROADMAP.md` → Admin Panel — Missing Sections. الرسومات عبر `twChart` (`static/shared/tw-chart.js`) بس — ❌ مكتبة رسوم. metric الرسم من allowlist بالسيرفر (`TIMESERIES_METRICS`) — ❌ اسم جدول / عمود من الطلب.

13. **السجل الأمني (SYSTEMS_INDEX §25b):** كل كتابة أدمن (`POST/PUT/PATCH/DELETE` تحت `/admin/`) + كل محاولة دخول أدمن (ناجحة / فاشلة) بتتسجّل من مكان واحد: `admin_audit_middleware` بـ `server.py`. ❌ تسجيل body / كلمة سر / توكن / نص رسالة · ❌ نداء تسجيل بكل endpoint · endpoint جديد للكتابة تحت `/admin/` بيتسجّل لحاله (ما في شي تعمله).

Test: `node tests/test_admin_shell_runtime.js` (registry → قائمة · ما في prefix · ما في تنفيذ بدون تأكيد · 401 → الدخول · قائمة جانبية / نافذة موبايل · بحث · حالة · رسم) · `python -m pytest tests/test_admin_insights.py -q` (endpoints + السجل).
