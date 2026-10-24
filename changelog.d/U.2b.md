## PR U.2b — TwPostCard: نقل سلوك أزرار المنشور وCSS للمكوّن المشترك (بدون تغيير) — 2026-10-24

- `static/shared/tw-post-card.js`: جديد `TwPostCard.create(opts)` → `{bind, trackViews, toggleComments}` — desired-state queue لأقدّر والحفظ (+ رجوع عند الفشل) · تتبّع المشاهدة · فتح / سكّر لوحة التعليقات · قائمة ⋯ · «المزيد / أقل» · المشاركة، منقولين من `company.posts.js` كما هم.
- الأجزاء الخاصة بالصفحة options / callbacks: `signedIn` · `paths` · `visitorKeyName` · `shareInfo` · `onEdit` / `onDelete` · `comments.build` / `load`.
- `company.posts.js`: انحذفت النسخ المنقولة؛ الصفحة بتستدعي `TwPostCard.create` بس · منطق التعليقات (§22c) ما تغيّر.
- جديد `static/shared/tw-card.css` = قسم `POST CARDS` من `company.css` (نفس الـ selectors والقيم) · بيتحمّل عبر `PAGE_ASSETS` قبل `company.css`.
- اختبار: `node tests/test_post_card_runtime.js` (سلوك على الـ markup الحقيقي + CSS = القسم المجمّد) · `test_post_save.py` 12–18 صاروا فحص سلوك · `test_company_colors.py` ما بيعدّ `.pc-btn--share:` كـ custom property.
- ما تغيّر شي بالشكل ولا بالسلوك ولا بشكل الطلبات.
