# AI Usage Budget — ترشيد الرصيد

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## AI Usage Budget — Minimal Execution (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions. The goal is to preserve token budget and deliver changes efficiently.

### Work pattern (every task)

1. Understand the request.
2. Read only the necessary files.
3. Make the change in the fewest files possible.
4. Run one or two targeted tests — no more.
5. If tests pass → open PR and send the report.
6. If tests fail twice → **stop**, report the reason, do not continue diagnosing.

### Test scope by change type

| نوع التعديل | الاختبار المطلوب |
|------------|----------------|
| تعديل CSS بسيط | فحص بصري مختصر أو اختبار واحد |
| تعديل JS بسيط | اختبار واحد مركز على السلوك المطلوب |
| تعديل حفظ / API frontend | اختبارات محددة للنجاح والفشل فقط |
| تعديل docs فقط | لا يحتاج tests |
| تعديل backend أو DB | توقف واشرح السبب قبل توسيع الفحص |

### Forbidden without prior report

Before doing any of the following, stop and send a short report:

- أكثر من 3 اختبارات لتعديل واحد
- إنشاء diagnostic script جديد
- تعديل test file فقط حتى ينجح (بدون إصلاح الكود الحقيقي)
- تشغيل suite كامل أكثر من مرة
- Screenshots متعددة
- بحث طويل داخل ملفات كثيرة
- خطوات إضافية خارج نطاق المطلوب

The report must answer:
- ما المشكلة؟
- لماذا تحتاج توسع؟
- كم ملف ستلمس؟
- هل التوسع ضروري فعلاً؟
- هل يوجد حل أبسط؟

### Merge / Deploy rules

- **لا تدمج** إلا إذا قال المستخدم صراحةً "ادمج الآن".
- **لا تعمل deploy** إلا إذا طُلب صراحةً.
- افتح PR نظيف واترك الدمج للمستخدم.

### End-of-task report (mandatory)

Every completed task must end with:

- ماذا تم؟
- الملفات المعدلة.
- هل التعديل ضمن النطاق؟
- ما الاختبار الذي شغلته؟ وهل نجح؟
- هل يوجد شيء لم يُختبر؟
- هل PR جاهز للدمج؟

### Screenshots

لا تلتقط screenshots إلا إذا:
- طلب المستخدم صراحةً، أو
- الخطأ بصري ولا يمكن فهمه بدون صورة.

### The golden rule

> اشتغل بذكاء، مش بكثرة خطوات.
> إذا المشكلة تحتاج تشخيص طويل، توقف واسأل قبل ما تستهلك الرصيد.
