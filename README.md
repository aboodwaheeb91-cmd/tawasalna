# تواصلنا (Tawasalna)

منصة توظيف عربية (RTL) تخدم ثلاثة أنواع حسابات: موظف (`emp`) · شركة (`co`) · جهة تعليمية (`edu`).
تشمل: بروفايلات عامة على `/u/{tw_id}`، نشر الوظائف والتقديم عليها وإدارة المرشحين، منشورات الشركات مع التعليقات والتقدير، الرسائل المباشرة (WebSocket)، الإشعارات، المواعيد، وتوثيق الشهادات من لوحة الأدمن.

- **Backend:** FastAPI — `server.py` (routes / JWT / WebSocket / migrations) + `auth.py` (طبقة البيانات والمنطق)
- **Database:** PostgreSQL على Supabase (`pg8000` / `asyncpg`)
- **Frontend:** HTML / CSS / Vanilla JS — بدون framework وبدون build step
- **Deployment:** Railway عبر `Procfile`

## التشغيل المحلي

```bash
pip install -r requirements.txt

export SUPABASE_DB_URL="postgres://..."
export JWT_SECRET="<random 32+ byte hex>"
export APP_ENV=development

uvicorn server:app --reload     # http://localhost:8000
```

الجداول والـ migrations تُنشأ تلقائياً عند التشغيل.

## Environment Variables

| Variable | مطلوب | الغرض |
|----------|-------|-------|
| `SUPABASE_DB_URL` | نعم | اتصال PostgreSQL |
| `JWT_SECRET` | نعم | توقيع JWT للمستخدمين |
| `ADMIN_TOKEN` | للأدمن | كلمة دخول الأدمن + `X-Admin-Token` |
| `ADMIN_URL_TOKEN` | للأدمن | مسار لوحة الأدمن `/tw-ctrl-{ADMIN_URL_TOKEN}` |
| `SCHEDULER_SECRET` | للـ scheduler | `X-Scheduler-Secret` للـ endpoints الداخلية |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | للرفع | Supabase Storage |
| `REDIS_URL` | اختياري | cache (fallback في الذاكرة) |
| `WS_ALLOWED_ORIGINS` | اختياري | allowlist لـ WebSocket origins (`*` ممنوع) |
| `APP_ENV` | اختياري | `production` (افتراضي) / `development` |
| `PORT` | تلقائي على Railway | منفذ السيرفر |

القائمة الكاملة مع التفاصيل: [`CLAUDE.md → Environment Variables`](CLAUDE.md#environment-variables).

## الاختبارات

اختبارات مركّزة في جذر الريبو (`test_*.py`, `test_*_runtime.js`) وفي `tests/`. شغّل الاختبار المرتبط بتعديلك فقط، مثلاً:

```bash
python -m pytest test_post_comments.py -q
node test_stale_session_entry_runtime.js
```

## التوثيق

- [`CLAUDE.md`](CLAUDE.md) — بروتوكول المهام وقواعد العمل الإلزامية (يبدأ به أي مطوّر أو جلسة AI)
- [`ARCHITECTURE_FOUNDATION.md`](ARCHITECTURE_FOUNDATION.md) — الدستور المعماري (فهرس القواعد F1–F37 بأول الملف)
- [`docs/SYSTEMS_INDEX.md`](docs/SYSTEMS_INDEX.md) — فهرس الأنظمة
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — المواصفات التقنية التفصيلية
