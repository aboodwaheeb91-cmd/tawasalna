# Tawasolna Design System — Index

> **ملاحظة للـ AI:** هذا الملف راوتر/فهرس فقط.
> لا تقرأ أي System File كاملاً تلقائياً — اقرأ فقط الأقسام المرتبطة بمهمتك.

---

## AI Reading Protocol

**قبل أي تنفيذ أو تعديل يمس زراً أو عنصراً تفاعلياً:**

1. ابدأ من جدول **Quick Routes** أدناه.
2. حدِّد نوع مهمتك.
3. افتح الملف المرتبط واقرأ **الأقسام المحددة فقط** — لا تقرأ الملف كاملاً.
4. إذا لم يوجد Route مناسب → **BTN-01 → STOP** → اسأل صاحب المشروع.
5. تحقق من أن التعديل لا يخالف قواعد "Forbidden Patterns" في القسم ذي الصلة.

**هدف هذا النظام:** تقليل Context/Token وتركيز القراءة على ما يخص المهمة فعلاً.
لا تقرأ عشرات القواعد غير المرتبطة بمهمتك.

---

## Quick Routes

| المهمة | الملف | الأقسام |
|--------|-------|---------|
| زر حفظ / إرسال | [BUTTONS.md](design-system/BUTTONS.md) | BTN-09 + BTN-07 |
| Toggle Button (bookmark، follow) | [BUTTONS.md](design-system/BUTTONS.md) | BTN-10 + BTN-07 |
| Icon Button (header، toolbar) | [BUTTONS.md](design-system/BUTTONS.md) | BTN-06 + BTN-07 |
| Navigation / Tab / رابط | [BUTTONS.md](design-system/BUTTONS.md) | BTN-12 + BTN-11 |
| إجراء خطير / حذف | [BUTTONS.md](design-system/BUTTONS.md) | BTN-13 + BTN-11 |
| زر جديد معروف النوع | [BUTTONS.md](design-system/BUTTONS.md) | BTN-02 → BTN-03 → BTN-04 → BTN-11 |
| نوع زر غير معروف | [BUTTONS.md](design-system/BUTTONS.md) | **BTN-00 → BTN-01 → STOP** |

> **إذا لم يوجد Route مناسب:**
> لا تختر أقرب نظام. **STOP** واسأل صاحب المشروع.

---

## Systems Table

| كود | النظام | الملف | الحالة |
|-----|--------|-------|--------|
| [DS-BTN] | Button System V1 | [design-system/BUTTONS.md](design-system/BUTTONS.md) | مستقر |

---

## Implementation Status

| طبقة | الحالة |
|------|--------|
| Documentation (هذا الملف + BUTTONS.md) | مكتمل ✓ |
| CSS Layer (`static/shared/tw-ui-tokens.css`) | **لم تُنشأ بعد** — انظر FUTURE_ROADMAP.md |

> `tw-ui-tokens.css` **ممنوع إنشاؤها** حتى يُطلب صراحةً.
> التوثيق الحالي يصف الـ contract المعماري فقط — ليس تنفيذاً CSS.

---

## Scope

نظام التصميم يخص:
- **Web:** صفحات HTML/CSS/JS في هذا المشروع
- **المستقبل:** Flutter (F1 — Platform, Not Website)

لا يخص:
- صفحات خارجية أو مشاريع أخرى
- CSS framework أو build step (لا يوجد — F7)
