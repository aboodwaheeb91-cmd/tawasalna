# Overlay System (DS-OVL) — Runtime V1

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتفتح نافذة / تأكيد / تنبيه أو بتلمس صفحة فيها `alert` / `confirm` / `prompt`.
> القاعدة العليا: `ARCHITECTURE_FOUNDATION.md` → F33. المواصفة: `docs/design-system/OVERLAY-SYSTEM.md` (العقد OVL-00 → OVL-38 · الـ Runtime **OVL-39**).

## DS-OVL Rules (mandatory for all AI sessions)

1. **ملف واحد:** `static/shared/tw-overlay.js` هو الـ Runtime الوحيد للنوافذ — `twConfirm` · `twAlert` · `twModal`. ممنوع نسخة تانية أو engine محلي بصفحة.

2. **التأكيد:** `twConfirm({title, message, confirmText, cancelText, danger})` → `Promise<boolean>`. إجراء نهائي / خطِر (حذف، إغلاق نهائي، إلغاء) → `danger: true` (زر بلون الخطر، الـ focus الأول على «إلغاء»، الخلفية ما بتسكّر).

3. **التنبيه:** `twAlert({title, message})` → `Promise` — بس لرسالة لازم تنقرا قبل ما يكمّل. نجاح / خطأ عادي = `showToast` (DS-FEEDBACK — F34).

4. **نافذة بمحتوى:** `twModal({title, content, actions, dismissible, onClose})` → `{close, setBusy, el}`. `onClick` بيرجّع Promise = busy (Escape والخلفية ما بيسكّروا لحتى يخلص). بدل `prompt()` والمودالات اليدوية الجديدة.

5. **السلوك ملك النظام:** role=dialog + aria-modal + aria-labelledby · Escape · focus trap · رجوع الـ focus · `inert` للخلفية · scroll lock — كلّه جوّا `tw-overlay.js`. الصفحة ما بتكتب ولا وحدة منهن لنافذة جديدة.
   - **Escape + قائمة منسدلة مفتوحة (PR 3.10):** `tw-select.js` بيمسك Escape على `window` (capture) وهي مفتوحة → `preventDefault` + `stopPropagation` + بيسكّر القائمة بس؛ و `tw-overlay.js` بيتجاهل Escape إذا `event.defaultPrevented`. الضغطة الجاية بتسكّر النافذة. Test: `node tests/test_ds_overlay_runtime.js` (القسم E).

6. **التحميل:** أصل صفحة عبر `PAGE_ASSETS` بـ `page_shell.py` — `<script src="/static/shared/tw-overlay.js?v={{v:tw-overlay.js}}">` بعد `<!--tw:shell-scripts-->` (وبعد `tw-icons.js`). مش بالـ Page Shell.

7. **الشكل:** DS-COLOR / DS-SIZE / DS-ICON بس — ممنوع hex / rgba أو px جديد بالملف. النصوص عربي، `dir="rtl"`.

8. **الترحيل تدريجي (OVL-29):** **أي صفحة بتنلمس من هلق** → `alert` / `confirm` / `prompt` فيها بيصيروا DS-OVL بنفس الـ PR. المرجع: `appointment-room.html`. ما في Big Bang — باقي الصفحات وقت ما تنلمس. لا تفتح نافذة DS-OVL فوق مودال يدوي مفتوح ولا العكس.

### Forbidden (permanent)

```
❌ alert() / confirm() / prompt() (أو window.*) بصفحة بتنلمس من هلق
❌ مودال / حوار تأكيد جديد مكتوب يدوي — twModal / twConfirm
❌ Escape listener / focus trap / body overflow محلي لنافذة جديدة
❌ نسخة تانية من twConfirm / scConfirm جديد
❌ tw-overlay.js بالـ Page Shell
❌ لون أو حجم برّا الـ tokens جوّا tw-overlay.js
```

Test: `node tests/test_ds_overlay_runtime.js` — فيه **REPORT** بيعدّ `alert` / `confirm` / `prompt` الباقيين بالموقع (تقرير بس، مش فشل).
