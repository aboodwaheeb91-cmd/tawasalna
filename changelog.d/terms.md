## PR terms — صفحتا سياسة الخصوصية وشروط الاستخدام + موافقة إجبارية بالتسجيل — 2026-10-23

- صفحتين عامتين جديدتين `/privacy` و `/terms` (Page Shell + الهيدر الموحّد): مسودة عربية حسب القانون الأردني، فوق كل صفحة ملاحظة «مسودة قيد المراجعة القانونية» + رقم الإصدار. المحتوى مبني على اللي الموقع فعلياً بيجمعه (الحساب · الملف · التوثيق بصورة الهوية · الرسائل · طلبات التوظيف · المواعيد · المشاهدات · الإشعارات والبريد · IP لأقفال الدخول وتحديد الدولة · التخزين بالمتصفح) ومزوّدي الخدمة (Railway · Supabase · Resend · ip-api.com · Google Fonts). كل النصوص مفاتيح `twT` (`legal.*`)، وإيميل التواصل `CONTACT_EMAIL_TBD` بمفتاح `legal.contact_email`.
- روابط للصفحتين بفوتر الـ landing وبنموذج التسجيل.
- التسجيل: checkbox إجباري «أوافق على شروط الاستخدام وسياسة الخصوصية». السيرفر بيرفض بدون `terms_accepted: true` → 422 `terms_required` (ما في شي بينكتب). مع الموافقة بينخزّن `users.terms_accepted_at` + `users.terms_version` (`tw_terms.TERMS_VERSION` — قيمة السيرفر).
- migration جديد `terms_acceptance` بـ `tw_terms.py` (حرج، عمودين nullable على `users`، بدون backfill). المستخدمين الحاليين ما بينطلب منهم موافقة جديدة (نقطة مفتوحة).
- الصفحتين قابلين للفهرسة (`_INDEXABLE_PAGES` + sitemap).
- اختبار: `python -m pytest tests/test_terms_acceptance.py -q` + `node tests/test_login_jobdetail_runtime.js` (C13 / C14).
