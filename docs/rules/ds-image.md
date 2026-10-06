# Image Display System V1 (DS-IMAGE)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتعرض صورة حساب (أفاتار / لوغو / غلاف) أو بتحط رابط صورة من الـ API بالـ DOM.
> القاعدة العليا: `ARCHITECTURE_FOUNDATION.md` → F38. المواصفة الكاملة: `docs/design-system/IMAGE-SYSTEM.md` (IMG-00 → IMG-13).

## Image Display System V1 (DS-IMAGE) Rules (mandatory for all AI sessions)

1. **ابدأ من IMG-00.** أي صورة حساب → IMG-00 (Routing Protocol) أولاً.

2. **دالة واحدة:** `twAvatarHtml(entity, size, opts)` (string) و `twAvatarEl(entity, size, opts)` (عنصر) بـ `tw_shared.js`. `entity = { full_name, avatar_url, user_type }` · `size` = `md` | `lg` | `xl` | `2xl` · `opts.eager` للـ hero فقط.

3. **رابط الصورة (IMG-08 · §54):** `twSafeImageUrl(url)` هو الفحص الوحيد (`https://` أو `/` نسبي). `background-image` فقط عبر `twCssUrl(url)`. بالـ HTML string → `twEscAttr(twSafeImageUrl(url))`؛ بالـ DOM → `img.src = twSafeImageUrl(url)` (بدون escaping).

4. **الأحجام (IMG-02):** `--size-avatar-md/lg/xl/2xl` (40/48/88/106) بـ DS-SIZE. 22 / 32 مجمّدة (SIZE-08). توحيد القيم القريبة = مرئي → المرحلة C مع screenshots.

5. **الشكل (IMG-03):** emp دائرة · co / edu مربع بزوايا (md `--radius-md` · lg `--radius-lg` · xl / 2xl `--radius-3xl`) بكل مكان.

6. **الحرف البديل (IMG-04/05):** `Array.from(name.trim())[0]` بدون `toUpperCase`، وإلا `؟`. اللون categorical (emp teal · co blue · edu purple). بدون hex.

7. **الفشل (IMG-06/07):** `data-fb="1"` على `[data-tw-ava]` — listener واحد capture على `document`. ممنوع `onerror` inline.

8. **الغلاف (IMG-10):** 4:1 للموظف والشركة — التنفيذ بالمرحلة C.

9. **المرحلة C صفحة صفحة بموافقة صريحة** (messages ← company ← profile ← home / job-detail). لحد هداك ما في صفحة بتستعمل `twAvatar*`.

### Forbidden (permanent)

```
❌ New avatar / logo markup in a page instead of twAvatarHtml / twAvatarEl
❌ Local image-URL regex instead of twSafeImageUrl · background-image without twCssUrl
❌ img.src = esc(url) · src="' + esc(url) + '" (HTML escaping is not URL validation)
❌ Inline onerror · emoji fallback · letter via toUpperCase / charAt(0)
❌ Raw px / hex for avatar size, radius or fallback colour
❌ Circle for an org (co / edu) logo · square for an employee avatar
❌ A second avatar helper / second error listener
❌ DS-IMAGE phase C on a page without explicit approval for that page
```

Test: `node test_ds_image_runtime.js`.
