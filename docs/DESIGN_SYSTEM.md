# Tawasolna Design System — Index

> **ملاحظة للـ AI:** هذا الملف راوتر/فهرس فقط. لا تقرأ فقط هذا الملف وتكمل.
> اقرأ الملف المرتبط بالنظام الذي تعمل عليه قبل أي تعديل.

---

## AI Reading Protocol

**قبل أي تعديل يمس زر أو عنصر تفاعلي:**

1. ابحث في الجدول أدناه عن النظام المناسب.
2. اقرأ الملف المرتبط كاملاً.
3. تحقق من أن التعديل لا يخالف أياً من قواعد "Forbidden Patterns" في ذلك الملف.
4. اتبع الـ contract الموثَّق — لا تخترعه من جديد.

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
