# Size System V1 (DS-SIZE)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة تلمس أحجام الخط أو الزوايا أو المسافات أو الأيقونات أو ارتفاعات الأزرار.
> القاعدة العليا: `ARCHITECTURE_FOUNDATION.md` → F36. المواصفة الكاملة: `docs/design-system/SIZE-SYSTEM.md` (SIZE-00 → SIZE-12).

## Size System V1 (DS-SIZE) Rules (mandatory for all AI sessions)

1. **ابدأ من SIZE-00.** أي مهمة فيها `font-size` / `border-radius` / `padding` / `margin` / `gap` / حجم أيقونة / ارتفاع زر → SIZE-00 (Routing Protocol) أولاً.

2. **Namespaces محجوزة:** `--size-*` و `--radius-*` و `--space-*` تُعرَّف **فقط** بـ `tw_shared.css` (قسم `1b. DS-SIZE`). أي ملف CSS/HTML/JS آخر ممنوع يعرّفها أو يعيد تعريفها.

3. **كود جديد يستعمل الـ tokens.** قيمة خام جديدة برّا السلّم لازم سبب بوصف الـ PR (SIZE-09).

4. **Migration = المطابق وتحت البكسل فقط** (فرق < 0.5px). القيم المرئية (≥ 0.5px) ما بتدخل migration — بتروح لـ PR redesign معلن لكل صفحة مع screenshots. الاستثناء الوحيد المعتمد: أيقونات 13px → `--size-icon-sm` (قرار 2) ويُذكر بوصف الـ PR.

5. **Phase 2 (migration) بموافقة صريحة لكل صفحة.** Phase 1 = tokens فقط، ما في selector بيستهلكها.

6. **Tiers (SIZE-07):** T1 عالمي بـ `tw_shared.css` · T2 alias محلي بيشاور على T1 (`--r-sm: var(--radius-md)`) — بدون قيمة خام · T3 قيمة محلية موثقة.

7. **`--radius-control` = `var(--radius-md)` (10px)** هو radius الأزرار والحقول (BTN-02).

8a. **أحجام الأفاتار (PR-7b):** `--size-avatar-md/lg/xl/2xl` (40/48/88/106) — مالكها DS-IMAGE (`docs/rules/ds-image.md`)؛ مستهلكها `.tw-ava` فقط.

8. **الاستثناءات المجمّدة (SIZE-08) ممنوع تنلمس:** `.sc-actions` / `.sc-btn` (profile-v2) وقيم post-comments (28px reply indent، avatar 32/22، max-height 280px) — حتى القيم المطابقة جوّاها.

9. **ما في tokens للمسافات الفردية** (3/5/7/9/11/13px) — تبقى محلية لحد redesign معلن (قرار 5).

10. **أزرار الهيدر (32/34/40) بدون قرار** — توحيدها PR بصري منفصل فقط (قرار 4).

11. **ممنوع نسخ الـ tokens** لصفحة ما بتحمّل `tw_shared.css` — الحل تحويلها للـ Page Shell (F39) مع فحص بصري (appointments + appointment-room ✅ Phase C).

### Forbidden (permanent)

```
❌ --size-* / --radius-* / --space-* defined outside tw_shared.css
❌ Visible-difference value replaced inside a migration PR
❌ Touching .sc-actions / .sc-btn or post-comments frozen values in a DS-SIZE migration
❌ Tokens for odd spacings (3/5/7/9/11/13px) or for the 36px button height
❌ Forcing height on input fields
❌ Changing any DS-SIZE token value without a declared DS-SIZE PR
❌ A parallel size system / second tokens file (e.g. tw-ui-tokens.css)
```

Test: `python test_ds_size_tokens.py`.
