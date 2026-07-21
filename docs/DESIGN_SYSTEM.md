# Tawasolna Design System — Index

> **ملاحظة للـ AI:** هذا الملف راوتر/فهرس فقط.
> لا تقرأ أي System File كاملاً تلقائياً — اقرأ فقط الأقسام المرتبطة بمهمتك.

---

## AI Reading Protocol

**قبل أي تنفيذ أو تعديل يمس زراً أو عنصراً تفاعلياً أو صلاحية أو navigation أو نموذج إدخال:**

1. ابدأ من جدول **Quick Routes** أدناه.
2. حدِّد نوع مهمتك.
3. افتح الملف المرتبط واقرأ **الأقسام المحددة فقط** — لا تقرأ الملف كاملاً.
4. إذا لم يوجد Route مناسب → **STOP** → اسأل صاحب المشروع. لا تختر أقرب نظام. (F30)
5. تحقق من أن التعديل لا يخالف قواعد "Forbidden Patterns" في القسم ذي الصلة.
6. قبل كتابة الكود: حدِّد النظام الذي ينتمي إليه كل جزء (F31 — System Routing Before Implementation).

**هدف هذا النظام:** تقليل Context/Token وتركيز القراءة على ما يخص المهمة فعلاً.
لا تقرأ عشرات القواعد غير المرتبطة بمهمتك.

---

## Quick Routes

| المهمة | الملف | الأقسام |
|--------|-------|---------|
| زر حفظ / إرسال | [BUTTONS.md](design-system/BUTTONS.md) | BTN-09 + BTN-07 |
| Toggle Button (bookmark، follow) | [BUTTONS.md](design-system/BUTTONS.md) | BTN-10 + BTN-07 |
| Icon Button (header، toolbar) | [BUTTONS.md](design-system/BUTTONS.md) | BTN-06 + BTN-07 |
| Navigation / Tab / رابط (دلالة العنصر) | [BUTTONS.md](design-system/BUTTONS.md) | BTN-12 + BTN-11 |
| Navigation / Back / سلوك URL / route behavior | [NAVIGATION.md](design-system/NAVIGATION.md) | NAV-02 + BTN-12 |
| إجراء خطير / حذف | [BUTTONS.md](design-system/BUTTONS.md) | BTN-13 + BTN-11 |
| زر جديد معروف النوع | [BUTTONS.md](design-system/BUTTONS.md) | BTN-02 → BTN-03 → BTN-04 → BTN-11 |
| نوع زر غير معروف | [BUTTONS.md](design-system/BUTTONS.md) | **BTN-00 → BTN-01 → STOP** |
| زر مرتبط بصلاحية / Viewer Mode | [BUTTONS.md](design-system/BUTTONS.md) + [VIEWER-MODES.md](design-system/VIEWER-MODES.md) | **BTN-17** + VM-05 + VM-06 + VM-07 |
| من يرى عنصراً / تحديد Viewer Mode | [VIEWER-MODES.md](design-system/VIEWER-MODES.md) | VM-01 + VM-02 |
| فهم Authentication vs Authorization vs Ownership | [VIEWER-MODES.md](design-system/VIEWER-MODES.md) | VM-05 |
| Backend كمرجع نهائي للصلاحيات | [VIEWER-MODES.md](design-system/VIEWER-MODES.md) | VM-06 + VM-07 |
| Back Button / History / سلوك الرجوع | [NAVIGATION.md](design-system/NAVIGATION.md) | NAV-05 + NAV-06 |
| رابط navigation أو URL جديد | [NAVIGATION.md](design-system/NAVIGATION.md) | NAV-02 + BTN-12 |
| Deep Link / صفحة تعمل من URL مباشر | [NAVIGATION.md](design-system/NAVIGATION.md) | NAV-08 |
| Auth redirect + ?next= | [NAVIGATION.md](design-system/NAVIGATION.md) | NAV-10 + NAV-07 |
| بناء حقل إدخال (input / textarea) | [INPUT-FIELDS.md](design-system/INPUT-FIELDS.md) | INP-03 + INP-05 |
| حالة بصرية للحقل (Error / Focus / Disabled) | [INPUT-FIELDS.md](design-system/INPUT-FIELDS.md) | INP-05 |
| Label / Placeholder / Helper Text | [INPUT-FIELDS.md](design-system/INPUT-FIELDS.md) | INP-06 |
| Password / Email / URL / Tel field | [INPUT-FIELDS.md](design-system/INPUT-FIELDS.md) | INP-09 + INP-11 + INP-13 |
| فتح فورم Add أو Edit | [FORM-LIFECYCLE.md](design-system/FORM-LIFECYCLE.md) | FRM-04 + FRM-05 + FRM-06 |
| بناء Payload قبل الإرسال | [FORM-LIFECYCLE.md](design-system/FORM-LIFECYCLE.md) | FRM-09 |
| ما يحدث عند نجاح / فشل الحفظ | [FORM-LIFECYCLE.md](design-system/FORM-LIFECYCLE.md) | FRM-16 + FRM-21 |
| Dirty State / تحذير التغييرات | [FORM-LIFECYCLE.md](design-system/FORM-LIFECYCLE.md) | FRM-13 + FRM-14 |
| متى تظهر رسائل الخطأ (Timing) | [VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | VAL-05 |
| خطأ Backend على حقل محدد | [VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | VAL-07 + VAL-08 |
| خطأ عام / Form-level error | [VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | VAL-09 |
| تنظيف الأخطاء (Cleanup) | [VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | VAL-12 |
| صياغة رسالة خطأ | [VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | VAL-17 |
| Tri-state PATCH semantics | [API-MUTATIONS-ERRORS.md](contracts/API-MUTATIONS-ERRORS.md) | API-MUT-03 |
| شكل Error Response من Backend | [API-MUTATIONS-ERRORS.md](contracts/API-MUTATIONS-ERRORS.md) | API-MUT-08 + API-MUT-10 |
| تصنيف أخطاء HTTP | [API-MUTATIONS-ERRORS.md](contracts/API-MUTATIONS-ERRORS.md) | API-MUT-12 |

> **إذا لم يوجد Route مناسب في الجدول:**
> لا تختر أقرب نظام. **STOP** واسأل صاحب المشروع. (F30)
> الأنظمة الحالية: [DS-BTN] · [DS-VM] · [DS-NAV] · [DS-INP] · [DS-FRM] · [DS-VAL] · [API-MUT] — لا تبني نظاماً موازياً لأيٍّ منها.

---

## Systems Table

| كود | النظام | الملف | الحالة |
|-----|--------|-------|--------|
| [DS-BTN] | Button System V1 | [design-system/BUTTONS.md](design-system/BUTTONS.md) | مستقر |
| [DS-VM] | Viewer Modes & Permissions System V1 | [design-system/VIEWER-MODES.md](design-system/VIEWER-MODES.md) | مستقر |
| [DS-NAV] | Navigation System V1 | [design-system/NAVIGATION.md](design-system/NAVIGATION.md) | موثَّق — التنفيذ مؤجَّل |
| [DS-INP] | Input Fields System V1 | [design-system/INPUT-FIELDS.md](design-system/INPUT-FIELDS.md) | موثَّق — V1 (توثيق) |
| [DS-FRM] | Form Lifecycle System V1 | [design-system/FORM-LIFECYCLE.md](design-system/FORM-LIFECYCLE.md) | موثَّق — V1 (توثيق) |
| [DS-VAL] | Validation & Error Contract V1 | [design-system/VALIDATION-ERRORS.md](design-system/VALIDATION-ERRORS.md) | موثَّق — V1 (توثيق) |
| [API-MUT] | API Mutation & Error Contract V1 | [contracts/API-MUTATIONS-ERRORS.md](contracts/API-MUTATIONS-ERRORS.md) | موثَّق — V1 (توثيق) |

**أنظمة مستقبلية (لم تُوثَّق بعد — انظر INP-16 للقائمة الكاملة):**

| كود (مؤقت) | النظام | الحالة |
|-----------|--------|--------|
| [DS-SEL] | Select & Dropdown System | مؤجَّل — tw-select.js موجود لكن غير موثَّق في DESIGN_SYSTEM |
| [DS-OVL] | Overlay / Modal / Sheet System | مؤجَّل |
| [DS-REF] | Reference Data System | مؤجَّل — tw-options-data.js موجود |
| [DS-DATE] | Date & Time Picker System | مؤجَّل |
| [DS-PHONE] | Phone Input / Dial Code System | مؤجَّل |
| [DS-OTP] | OTP / Pin Input System | مؤجَّل |
| [DS-UPLOAD] | Upload Input UI System (drag & drop) | مؤجَّل — tw-upload.js يُغطي HTTP فقط |
| [DS-RICH] | Rich Text / WYSIWYG System | غير مخطط في V1 |
| [DS-MODERATION] | Content Moderation / Profanity Filter | مؤجَّل |
| [DS-FEEDBACK] | Toast / Snackbar / Feedback System | مؤجَّل |

> **قاعدة إلزامية (F30):** لا يُبنى على أي نظام في هذا الجدول حتى يُوثَّق في PR مستقل.
> إذا احتاجت المهمة أحد هذه الأنظمة — **STOP** واسأل صاحب المشروع.

---

## Implementation Status

| طبقة | الحالة |
|------|--------|
| Documentation — `BUTTONS.md` (BTN-00 → BTN-17) | مكتمل ✓ |
| Documentation — `VIEWER-MODES.md` (VM-00 → VM-09) | مكتمل ✓ |
| Documentation — `NAVIGATION.md` (NAV-00 → NAV-12) | مكتمل ✓ |
| Documentation — `INPUT-FIELDS.md` (INP-00 → INP-16) | مكتمل ✓ — V1 توثيق |
| Documentation — `FORM-LIFECYCLE.md` (FRM-00 → FRM-25) | مكتمل ✓ — V1 توثيق |
| Documentation — `VALIDATION-ERRORS.md` (VAL-00 → VAL-20) | مكتمل ✓ — V1 توثيق |
| Documentation — `contracts/API-MUTATIONS-ERRORS.md` (API-MUT-00 → API-MUT-18) | مكتمل ✓ — V1 توثيق |
| CSS Layer (`static/shared/tw-ui-tokens.css`) | **لم تُنشأ بعد** — انظر FUTURE_ROADMAP.md |
| Navigation Implementation (Layer Stack، Back Contract، ?next=) | **لم تُنفَّذ بعد** — موثَّقة في NAVIGATION.md |
| Input / Form / Validation Runtime Implementation | **لم تُنفَّذ بعد** — موثَّقة في INP/FRM/VAL |

> `tw-ui-tokens.css` **ممنوع إنشاؤها** حتى يُطلب صراحةً.
> `Navigation Implementation` **ممنوع تنفيذها** حتى يُطلب صراحةً.
> `Input/Form/Validation Runtime` **ممنوع تنفيذها** حتى يُطلب صراحةً.
> التوثيق الحالي يصف الـ contracts المعمارية فقط — ليس تنفيذاً.

---

## Scope

نظام التصميم يخص:
- **Web:** صفحات HTML/CSS/JS في هذا المشروع
- **المستقبل:** Flutter (F1 — Platform, Not Website)

لا يخص:
- صفحات خارجية أو مشاريع أخرى
- CSS framework أو build step (لا يوجد — F7)
