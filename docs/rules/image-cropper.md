# Image Cropper — قص الصور

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Image Cropper System Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
**Status: Implemented & Stable (PR #404–#408). All 4 image types wired to TW.createCropper.**

1. **`static/shared/tw-image-cropper.js` exists and is stable.** Do NOT modify it without a documented bug reason stated before any edit. Do NOT duplicate its logic in any page module.

2. **`tw-image-cropper.js` and `tw-upload.js` are permanently separate systems.** The cropper outputs a `dataUrl`. The uploader takes a `dataUrl`. Neither knows about the other. Do NOT merge crop logic into `tw-upload.js` or upload logic into `tw-image-cropper.js`.

3. **Any new image type that needs crop/zoom/drag MUST use `TW.createCropper()`.** Adding inline crop code to any page module is permanently forbidden — the shared cropper exists and must be used.

4. **Each image type has a frozen config** (documented in `ARCHITECTURE.md → Image Cropper Architecture`). Do not deviate:
   - `employee-avatar`: ratio 1/1, shape circle (preview only), output 260×260, quality 0.85, bucket avatars, filename avatar — `profile-v2.avatar.js`
   - `employee-cover`: ratio 6/1, shape rect, output 720×120, quality 0.88, bucket covers, filename cover — `profile-v2.cover.js`
   - `company-logo`: ratio 1/1, shape circle (preview only), output 300×300, quality 0.85, bucket avatars, filename logo — `company.main.js`
   - `company-cover`: ratio 4/1, shape rect, output 800×200, quality 0.88, bucket avatars, filename cover — `company.main.js`

5. **CSS ratio must match output ratio.** `employee-cover` CSS is `aspect-ratio:6/1`, export is 720×120 (6:1). `company-cover` CSS is `aspect-ratio:4/1`, export must be 800×200 (4:1). A mismatch causes visual distortion.

6. **All implementation phases are complete (PR #403–#409).** No further phased rollout is needed. Any new image type follows the established pattern directly.

7. **`tw-upload.js` must not change** as part of any cropper PR. The upload contract (`TW.uploadImage` signature, return shape, endpoint) is frozen.

8. **Forbidden patterns (permanent):**
   ```
   ❌ Adding crop canvas/zoom/drag inline to any page module
   ❌ Merging crop logic into tw-upload.js
   ❌ Changing output dimensions without updating the config table in ARCHITECTURE.md
   ❌ Showing crop UI to public/guest viewers (owner-only CSS class is mandatory)
   ❌ A new image type PR that does not use TW.createCropper
   ❌ Modifying tw-image-cropper.js without stating a documented bug reason first
   ```
