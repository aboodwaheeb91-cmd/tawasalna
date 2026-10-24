## PR U.3 — TwPostCard: تنظيف المكوّن (twT · DS-ICON · DS-IMAGE · توكنز · وقت نسبي · السجل) + `--color-action-save` — 2026-10-24

- `static/shared/tw-post-card.js`: كل نص من `twT` (`post.card.*` · `action.share`) · 12 SVG يدوي → `twIcon` · اللوغو `twAvatarHtml` (خيار جديد `opts.authorType`) · الوقت `twRelativeTime` · الأزرار من السجل عبر `twActionState` (+ `type="button"` + `data-tw-action`). API ما تغيّر.
- `tw_actions.json`: `post_appreciate` · `post_save` · `post_comment` (`visibleWhen: comments_enabled`) · `post_edit` · `post_delete` · `tw_actions.py` + `tw_shared.js`: `comments_enabled` → `ctx.commentsEnabled`.
- `tw_shared.js`: جديد `twRelativeTime(value)` (`time.rel.*`، بعد 30 يوم `twFormatDate`) — SYSTEMS_INDEX §59a.
- `tw_shared.css`: token جديد `--color-action-save` (+`-rgb`) = `sky-400` (Q3 مُجاب) · `static/shared/tw-card.css`: الحفظ الفعّال بيستعمله بدل لون التحذير · كل الأحجام من `--space-*` / `--radius-*` / `--size-*`.
- تغيير سلوك: الضيف على «أقدّر» / «حفظ» → صفحة الدخول (`twLoginHref`) بدل toast.
- اختبار: `node tests/test_post_card_runtime.js` (صار سلوكي — انحذفت النسختين المجمّدتين) · `test_post_save.py` 10 / 14.
