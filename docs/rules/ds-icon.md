# Icon System V1 (DS-ICON)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتعرض أو بتضيف أو بتغيّر أيقونة واجهة.
> القاعدة العليا: `ARCHITECTURE_FOUNDATION.md` → F37. المواصفة الكاملة: `docs/design-system/ICON-SYSTEM.md` (ICON-00 → ICON-14).

## Icon System V1 (DS-ICON) Rules (mandatory for all AI sessions)

1. **ابدأ من ICON-00.** أي أيقونة → ICON-00 (Routing Protocol) أولاً.

2. **Registry واحد:** `static/shared/tw-icons.js` هو المصدر الوحيد — `twIcon(name, opts)` (string) و `twIconEl(name, opts)` (عنصر). مستقل عن `tw_shared.js` / `tw_shared.css`. أيقونات الـ HTML الثابتة = `<i data-tw-icon="name" data-tw-size="sm">` + `twIcon.hydrate(root)` مرّة وحدة بالـ init (ICON-03.1) — ممنوع دالة محلية تلزّقها. اختبار: `node test_auth_next_icon_hydrate_runtime.js` (C).

3. **الرسومات من Lucide 0.460.0 فقط** (ISC — `THIRD_PARTY_NOTICES.md`). لا مكتبة ثانية، لا رسم يدوي، لا نسخة ثانية.

4. **الأسماء (ICON-04):** أفعال وتنقّل = اسم المعنى (`back` · `close` · `delete` · `edit` · `more`…) · أشياء = اسم Lucide · الكتالوج = الاسم المخزَّن بالـ DB حرفياً. الأسماء القديمة → جدول `ALIASES` الوحيد بـ `tw-icons.js`.

5. **الاتجاه (ICON-08):** `back` / `forward` / `prev` / `next` / `send` / `log-in` / `log-out` = `dir:true` وبتنقلب تلقائياً بالـ RTL (class `tw-ico-dir` + قاعدة وحدة بيحقنها الملف). ممنوع `arrow-left` / `arrow-right` / `chevron-left` / `chevron-right` يدوي بالصفحات.

6. **الحجم (ICON-05):** `opts.size` = اسم token من DS-SIZE (`xs`…`2xl`) → `var(--size-icon-X, <px>)`. الأحجام برّا السلّم (10/11/15/19/24) بتتوحّد وقت تحويل كل صفحة؛ 26/28/40 محلية Tier 3.

7. **اللون (ICON-06):** `currentColor` فقط — اللون من العنصر الأب عبر DS-COLOR.

8. **السماكة (ICON-07):** 2 افتراضي. `.sc-btn .ico-sm` (1.8) مجمّد بالـ CSS تبعه. ما في خيار stroke-width بالـ API.

9. **الأمان (ICON-09):** الاسم ما بيدخل الـ HTML أبداً؛ اسم غير معروف → `help` + warning مرّة وحدة.

10. **emoji ممنوعة كأيقونة واجهة (ICON-11).** الموجودة بتنستبدل ضمن تحويل كل صفحة (المرحلة C)، admin بالآخر.

11. **أيقونة جديدة (ICON-12):** مدخل بالـ registry + مستهلك حقيقي بنفس الـ PR + الاختبار أخضر. مهارة/مهنة جديدة بالـ seed → أيقونتها بالـ registry بنفس الـ PR.

12. **المرحلة C صفحة صفحة بموافقة صريحة.** الصفحات المحوّلة (بتحمّل `tw-icons.js` كسكربت صفحة بعد `<!--tw:shell-scripts-->` — مش بالـ shell): `job-detail.html` · `landing.html` · `appointments.html` · `appointment-room.html`. أي صفحة جديدة بتنضاف لـ `PHASE_C_PAGES` بـ `test_ds_icon_registry.js` بنفس الـ PR.

### Forbidden (permanent)

```
❌ Second icon library / Lucide version other than 0.460 / new icon CDN
❌ New inline <svg> icon or new <i data-lucide> in any page
❌ Icon name concatenated into HTML (data-lucide="' + name + '")
❌ Manual arrow-left / arrow-right / chevron-left / chevron-right — use back / forward / prev / next
❌ Icon colour other than currentColor · per-call stroke-width
❌ Emoji as a UI icon
❌ Registry entry without a real consumer
❌ A second registry / page-local icon map / second alias table
❌ Loading tw-icons.js in a page outside that page's phase-C PR
```

Test: `node test_ds_icon_registry.js`.
