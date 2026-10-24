## PR U.2 — TwPostCard: نقل بطاقة منشور صفحة الشركة لمكوّن مشترك (بدون تغيير بصري) — 2026-10-24

- جديد `static/shared/tw-post-card.js`: `TwPostCard.html(post, {authorName, avatarUrl, canEdit})` بيرسم بطاقة المنشور بنفس الـ DOM / الكلاسات / `data-*` / الـ escaping حرفياً · `apprButtonInner` / `saveButtonInner` · `initClamps` · `relativeTime` / `formatViews`.
- `company.render.js`: `_postCardHtml` صار wrapper داخلي فوق المكوّن (انشال من `window`) · انحذفوا `_initPostClamps` / `_relativeTime` / `_fmtViews` (انتقلوا للمكوّن).
- `company.posts.js`: أزرار أقدّر / حفظ بعد الضغط + عدّاد المشاهدات من المكوّن — انحذفت نسخ الـ SVG والنص المكررة (D2 / D3) و`_fmtViewsCount`.
- `company-profile.html` بيحمّل المكوّن (`PAGE_ASSETS` → `tw-post-card.js`).
- اختبار: `node tests/test_post_card_runtime.js` (مطابقة حرفية مع نسخة مجمّدة من الكود القديم + escape) · `tests/test_post_save.py` 10 / 11 صاروا فحص سلوك.
- ما تغيّر شي بالشكل ولا بالسلوك. لسا (U.2b): نقل السلوك (queue · المشاهدة · التعليقات · ⋯ · المشاركة) + `tw-card.css`.
